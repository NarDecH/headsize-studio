"""Verify a published release the way a user's installation will see it.

Publishing can look successful while the release is actually unusable: the
v1.0.0 notes shipped as a bare generated link, and its screenshots pointed at
files that do not exist, because GitHub renders a release body against the
repository root. Nothing in the build or the test suite catches that — only the
published release itself can be checked, so this tool checks it.

It reads only the public API and the attached assets (no token needed, although
``GITHUB_TOKEN`` raises the anonymous rate limit), and reports every finding as
``[ok]``/``[FAIL]``:

* the tag exists, is published, and carries a non-empty body;
* the updater picks a build for this platform and a ``SHA256SUMS.txt``;
* that checksum file lists the asset the updater would download;
* the release is the one a stable installation is offered;
* every link in the body resolves on the web.

``--download`` also fetches the asset and verifies it against the published
checksum, and ``--self-test`` runs the downloaded build's own self-test, which
is the closest thing to "a user installed this and it worked".

Run:

    python tools/verify_release.py                          # whatever is live now
    python tools/verify_release.py --tag v1.0.0
    python tools/verify_release.py --latest --download --self-test

The scheduled *Release watchdog* workflow runs the last form every day, so a
release that rots after publication (a moved asset, a link that stops
resolving) surfaces on its own instead of when a user hits it.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from headsize.update.github import GithubClient, GithubError, ReleaseInfo  # noqa: E402
from headsize.update.repo import resolve_repo  # noqa: E402
from headsize.update.updater import (  # noqa: E402
    Updater,
    arch_key,
    parse_checksums,
    pick_checksum_asset,
    platform_key,
)
from headsize.version import __version__  # noqa: E402

USER_AGENT = "HeadSizeStudio-ReleaseCheck"
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
SELF_TEST_MARKER = "[ok  ]"
SELF_TEST_FAILURE = "[FAIL"


@dataclass
class Finding:
    """One check, phrased so the log reads as a sentence."""

    name: str
    ok: bool
    detail: str = ""


@dataclass
class Report:
    slug: str
    tag: str
    channel: str = "stable"
    findings: list[Finding] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.findings.append(Finding(name, ok, detail))

    @property
    def failures(self) -> list[Finding]:
        return [f for f in self.findings if not f.ok]

    @property
    def ok(self) -> bool:
        return not self.failures

    def render(self) -> str:
        width = max((len(f.name) for f in self.findings), default=0)
        lines = [f"{self.slug} · {self.tag or 'latest ' + self.channel}"]
        for finding in self.findings:
            mark = "ok  " if finding.ok else "FAIL"
            lines.append(f"  [{mark}] {finding.name.ljust(width)}  {finding.detail}".rstrip())
        lines.append("")
        summary = "all checks passed" if self.ok else f"{len(self.failures)} check(s) failed"
        lines.append(summary)
        return "\n".join(lines)

    def as_json(self) -> dict:
        return {
            "slug": self.slug,
            "tag": self.tag,
            "channel": self.channel,
            "ok": self.ok,
            "findings": [asdict(f) for f in self.findings],
        }


def http_status(url: str, *, timeout: float = 20.0) -> int:
    """Status code for a URL, preferring HEAD but accepting a GET fallback."""
    for method in ("HEAD", "GET"):
        request = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
                return response.status
        except urllib.error.HTTPError as exc:
            if method == "HEAD" and exc.code in (403, 405):
                continue
            return exc.code
        except (urllib.error.URLError, TimeoutError, OSError):
            return 0
    return 0


def fetch_text(url: str, *, timeout: float = 30.0, token: str = "") -> str:
    headers = {"User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8", "replace")


def token_from_environment() -> str:
    """An optional token: only the rate limit and private releases need one."""
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def body_links(body: str) -> list[str]:
    """Every http(s) target in the release body, in order, without duplicates."""
    seen: list[str] = []
    for target in LINK.findall(body):
        if target.startswith(("http://", "https://")) and target not in seen:
            seen.append(target)
    return seen


def check_notes_links(
    report: Report,
    body: str,
    *,
    status: Callable[[str], int] = http_status,
) -> None:
    links = body_links(body)
    broken: list[str] = []
    for link in links:
        code = status(link)
        if code != 200:
            broken.append(f"{code} {link}")
    report.add(
        f"{len(links)} link(s) in the release notes resolve",
        not broken,
        "; ".join(broken),
    )


def as_text(value: bytes | str | None) -> str:
    """Console output of a packaged build is not always valid UTF-8 (see below)."""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value or ""


def check_self_test(
    report: Report,
    executable: Path,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> None:
    # The bundled build prints its report to a console that may not be UTF-8, so
    # the bytes are read and decoded here rather than by ``text=True``, which
    # raises on a stray byte and silences the report.
    env = dict(
        os.environ,
        QT_QPA_PLATFORM="offscreen",
        PYTHONUTF8="1",
        PYTHONIOENCODING="utf-8",
    )
    try:
        result = runner(
            [str(executable), "--self-test"],
            capture_output=True,
            timeout=300,
            env=env,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        report.add("published build passes its own self-test", False, str(exc))
        return
    stdout, stderr = as_text(result.stdout), as_text(result.stderr)
    output = stdout + stderr
    passed = result.returncode == 0 and SELF_TEST_FAILURE not in output
    # The report can go to both streams; count it once.
    counted = stdout if SELF_TEST_MARKER in stdout else output
    count = len(re.findall(r"^\[ok  \]", counted, re.MULTILINE))
    report.add(
        "published build passes its own self-test",
        passed,
        f"exit {result.returncode}, {count} checks reported",
    )


def verify(
    slug: str,
    tag: str = "",
    *,
    channel: str = "stable",
    client: GithubClient | None = None,
    download: bool = False,
    download_dir: Path | None = None,
    run_self_test: bool = False,
    status: Callable[[str], int] = http_status,
    read_text: Callable[[str], str] | None = None,
    platform_name: str | None = None,
    arch: str | None = None,
    token: str = "",
) -> Report:
    """Check one published release, or the live one when ``tag`` is empty.

    ``platform_name``/``arch`` default to this host.
    """
    owner, _, repo = slug.partition("/")
    client = client or GithubClient(owner, repo, token=token or None)
    if read_text is None:
        read_text = lambda url: fetch_text(url, token=token)  # noqa: E731
    report = Report(slug=slug, tag=tag, channel=channel)
    platform_name = platform_name or platform_key()
    arch = arch or arch_key()

    try:
        releases = client.list_releases()
    except GithubError as exc:
        detail = str(exc)
        if "rate limit" in detail.lower():
            detail += "  (an anonymous check allows 60 requests/hour; set GITHUB_TOKEN)"
        report.add(f"release {tag} can be read", False, detail)
        return report

    if tag:
        release: ReleaseInfo | None = next((r for r in releases if r.tag == tag), None)
        if release is None:
            report.add(f"release {tag} exists", False, "no such tag")
            return report
        report.add(f"release {tag} exists", True, release.html_url)
    else:
        # Ask the client, so an install's idea of "the latest release" and this
        # tool's idea cannot drift apart.
        release = client.latest_release(channel=channel)
        if release is None:
            report.add(f"a published {channel} release is available", False, "none found")
            return report
        report.tag = release.tag
        report.add(f"the live {channel} release is {release.tag}", True, release.html_url)
    report.add("release is published (not a draft)", not release.draft)
    report.add(
        "release body is not empty", bool(release.notes.strip()), f"{len(release.notes)} chars"
    )

    # The target platform has to reach the Updater: it is the object that picks
    # the asset, so a check aimed at another OS would otherwise silently grade
    # this host's build.
    updater = Updater(
        owner,
        repo,
        __version__,
        client=client,
        platform_name=platform_name,
        arch=arch,
    )
    asset = updater.asset_for(release)
    report.add(
        f"updater picks a build for {platform_name}/{arch}",
        asset is not None,
        asset.name if asset else "no asset matches this platform",
    )
    if asset is None:
        return report

    checksum = pick_checksum_asset(release)
    report.add(
        "SHA256SUMS.txt is attached", checksum is not None, checksum.name if checksum else ""
    )

    if checksum is not None:
        try:
            parsed = parse_checksums(read_text(checksum.url))
            digest = parsed.get(asset.name, "")
            report.add(
                f"{checksum.name} lists {asset.name}",
                bool(digest),
                digest[:16] + "…" if digest else "no line for this asset",
            )
        except (urllib.error.URLError, OSError) as exc:
            report.add(f"{checksum.name} can be downloaded", False, str(exc))

    latest = client.latest_release(channel=channel)
    report.add(
        f"a {channel} installation is offered this release",
        latest is not None and latest.tag == release.tag,
        latest.tag if latest else "no release offered",
    )

    check_notes_links(report, release.notes, status=status)

    if download or run_self_test:
        target = (
            Path(download_dir)
            if download_dir
            else Path(tempfile.mkdtemp(prefix="headsize-verify-"))
        )
        try:
            started = time.perf_counter()
            payload = updater.download(release, destination=target, require_checksum=True)
            elapsed = time.perf_counter() - started
            report.add(
                "downloaded asset matches the release metadata",
                payload.size == asset.size,
                f"{payload.size} bytes in {elapsed:.1f}s",
            )
            report.add(
                "download verified against the published SHA-256",
                payload.verified,
                payload.sha256[:16] + "…",
            )
            if run_self_test:
                check_self_test(report, payload.path)
        except (GithubError, OSError, RuntimeError) as exc:
            report.add("asset can be downloaded and verified", False, str(exc))
        finally:
            if download_dir is None:
                shutil.rmtree(target, ignore_errors=True)

    return report


def main(argv: Sequence[str] | None = None) -> int:
    owner, repo = resolve_repo()
    parser = argparse.ArgumentParser(description=__doc__)
    which = parser.add_mutually_exclusive_group()
    which.add_argument("--tag", default="", help="tag to verify")
    which.add_argument(
        "--latest",
        action="store_true",
        help="verify whatever release is live now (the default)",
    )
    parser.add_argument("--slug", default=f"{owner}/{repo}", help="owner/repo")
    parser.add_argument(
        "--channel",
        default="stable",
        choices=["stable", "beta"],
        help="release channel to look at with --latest",
    )
    parser.add_argument(
        "--download", action="store_true", help="fetch the asset and verify its checksum"
    )
    parser.add_argument(
        "--self-test", action="store_true", help="run the downloaded build's self-test"
    )
    parser.add_argument(
        "--platform",
        default="",
        choices=["", "windows", "macos", "linux"],
        help="check the build for another platform (default: this host)",
    )
    parser.add_argument("--arch", default="", help="check another architecture, e.g. arm64")
    parser.add_argument("--dest", help="where to keep the download (default: a temp folder)")
    parser.add_argument("--json", help="also write the report as JSON to this path")
    parser.add_argument(
        "--token",
        default="",
        help="GitHub token, or set GITHUB_TOKEN / GH_TOKEN, to raise the anonymous "
        "API rate limit",
    )
    args = parser.parse_args(argv)

    token = args.token or token_from_environment()
    report = verify(
        args.slug,
        args.tag,
        channel=args.channel,
        download=args.download or args.self_test,
        download_dir=Path(args.dest) if args.dest else None,
        run_self_test=args.self_test,
        platform_name=args.platform or None,
        arch=args.arch or None,
        token=token,
    )
    print(report.render())
    if args.json:
        Path(args.json).write_text(json.dumps(report.as_json(), indent=2), encoding="utf-8")
        print(f"report written to {args.json}")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
