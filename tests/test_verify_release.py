"""The published-release check: every finding, with the network faked out."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from headsize.update.github import GithubClient
from tools import verify_release

ROOT = Path(__file__).resolve().parent.parent

SLUG = "someone/headsize-studio"
TAG = "v1.2.3"
EXE = "HeadSize-Studio-1.2.3-windows-x64.exe"
DIGEST = "a" * 64


def release_json(
    *,
    tag: str = TAG,
    draft: bool = False,
    prerelease: bool = False,
    body: str = "Notes with a [link](https://example.com/notes).",
    assets: list[dict] | None = None,
) -> dict:
    default_assets = [
        {
            "name": EXE,
            "browser_download_url": f"https://example.com/download/{EXE}",
            "size": 1234,
        },
        {
            "name": "SHA256SUMS.txt",
            "browser_download_url": "https://example.com/download/SHA256SUMS.txt",
            "size": 105,
        },
    ]
    return {
        "tag_name": tag,
        "name": f"Release {tag}",
        "body": body,
        "draft": draft,
        "prerelease": prerelease,
        "html_url": f"https://github.com/{SLUG}/releases/tag/{tag}",
        "published_at": "2026-10-14T12:00:00Z",
        "assets": default_assets if assets is None else assets,
    }


def client_for(*releases: dict) -> GithubClient:
    return GithubClient("someone", "headsize-studio", fetch=lambda url: list(releases))


def run_verify(
    *releases: dict,
    tag: str = TAG,
    read_text=lambda url: f"{DIGEST}  {EXE}\n",
    status=lambda url: 200,
    **kwargs,
):
    return verify_release.verify(
        SLUG,
        tag,
        client=client_for(*releases),
        read_text=read_text,
        status=status,
        platform_name="windows",
        arch="x64",
        **kwargs,
    )


def test_a_healthy_release_passes_every_check() -> None:
    report = run_verify(release_json())

    assert report.ok, report.render()
    names = [f.name for f in report.findings]
    assert f"release {TAG} exists" in names
    assert any("updater picks a build" in name for name in names)
    assert any("SHA256SUMS.txt lists" in name for name in names)
    assert any("stable installation is offered" in name for name in names)
    assert report.findings[-1].name.endswith("resolve")


def test_a_missing_tag_fails_immediately() -> None:
    report = run_verify(release_json(tag="v0.1.0"), tag=TAG)

    assert not report.ok
    assert len(report.findings) == 1
    assert "no such tag" in report.findings[0].detail


def test_a_draft_release_is_rejected() -> None:
    """A draft is invisible to the updater, so it must fail both of those checks."""
    report = run_verify(release_json(draft=True))

    assert not report.ok
    assert [f.name for f in report.failures] == [
        "release is published (not a draft)",
        "a stable installation is offered this release",
    ]


def test_a_release_for_another_platform_is_reported() -> None:
    assets = [{"name": "HeadSize-Studio-1.2.3-macos-arm64.dmg", "size": 10}]
    report = run_verify(release_json(assets=assets))

    assert not report.ok
    assert any("no asset matches this platform" in f.detail for f in report.findings)


def test_missing_checksum_file_is_reported() -> None:
    assets = [{"name": EXE, "browser_download_url": "https://example.com/x.exe", "size": 10}]
    report = run_verify(release_json(assets=assets))

    assert not report.ok
    assert "SHA256SUMS.txt is attached" in [f.name for f in report.failures]


def test_checksum_file_without_the_asset_is_reported() -> None:
    report = run_verify(release_json(), read_text=lambda url: f"{DIGEST}  other-file.exe\n")

    assert not report.ok
    assert any("no line for this asset" in f.detail for f in report.failures)


def test_a_broken_link_in_the_notes_is_reported() -> None:
    body = "See [docs](https://example.com/missing.png) and [site](https://example.com/ok)."
    report = run_verify(
        release_json(body=body),
        status=lambda url: 404 if "missing" in url else 200,
    )

    links = report.findings[-1]
    assert not links.ok
    assert "404 https://example.com/missing.png" in links.detail


def test_an_empty_body_is_reported() -> None:
    report = run_verify(release_json(body=""))

    assert not report.ok
    assert "release body is not empty" in [f.name for f in report.failures]


@pytest.mark.parametrize(
    "body, expected",
    [
        ("[a](https://x.test/1)", ["https://x.test/1"]),
        ("![img](https://x.test/i.png)", ["https://x.test/i.png"]),
        ("[a](https://x.test/1) [b](https://x.test/1)", ["https://x.test/1"]),
        ("[rel](../CHANGELOG.md) [anchor](#top)", []),
    ],
)
def test_body_links_are_absolute_and_deduplicated(body: str, expected: list[str]) -> None:
    assert verify_release.body_links(body) == expected


def test_the_self_test_helper_reads_the_childs_verdict() -> None:
    report = verify_release.Report(slug=SLUG, tag=TAG)

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="[ok  ] one\n[ok  ] two\n", stderr=""
        )

    verify_release.check_self_test(report, Path("build.exe"), runner=runner)
    assert report.ok
    assert "2 checks reported" in report.findings[0].detail


def test_a_non_utf8_self_test_report_is_still_read() -> None:
    """The bundled build can print cp1252 bytes; that must not hide the report."""
    report = verify_release.Report(slug=SLUG, tag=TAG)

    def runner(*args, **kwargs):
        stdout = b"[ok  ] model present \x97 230 kB\n[ok  ] warp works\n"
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout=stdout, stderr=b""
        )

    verify_release.check_self_test(report, Path("build.exe"), runner=runner)
    assert report.ok
    assert "2 checks reported" in report.findings[0].detail


def test_a_report_on_both_streams_is_counted_once() -> None:
    report = verify_release.Report(slug=SLUG, tag=TAG)
    same = "[ok  ] one\n[ok  ] two\n"

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=same, stderr=same)

    verify_release.check_self_test(report, Path("build.exe"), runner=runner)
    assert "2 checks reported" in report.findings[0].detail


def test_a_failure_on_stderr_is_not_missed() -> None:
    report = verify_release.Report(slug=SLUG, tag=TAG)

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=0, stdout="[ok  ] one\n", stderr="[FAIL] two\n"
        )

    verify_release.check_self_test(report, Path("build.exe"), runner=runner)
    assert not report.ok


def test_the_self_test_helper_asks_the_child_for_utf8() -> None:
    seen: dict = {}

    def runner(*args, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    report = verify_release.Report(slug=SLUG, tag=TAG)
    verify_release.check_self_test(report, Path("build.exe"), runner=runner)
    assert seen["env"]["PYTHONIOENCODING"] == "utf-8"
    assert "text" not in seen, "text=True raises on a non-UTF-8 byte"


def test_a_failing_self_test_is_reported() -> None:
    report = verify_release.Report(slug=SLUG, tag=TAG)

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0], returncode=1, stdout="[ok  ] one\n[FAIL] two\n", stderr=""
        )

    verify_release.check_self_test(report, Path("build.exe"), runner=runner)
    assert not report.ok


def test_the_self_test_helper_survives_a_missing_binary() -> None:
    report = verify_release.Report(slug=SLUG, tag=TAG)
    verify_release.check_self_test(report, Path("definitely-not-here.exe"))
    assert not report.ok
    assert report.findings[0].detail


def test_a_rate_limited_check_says_what_to_do(monkeypatch: pytest.MonkeyPatch) -> None:
    from headsize.update.github import GithubError

    def boom(url: str):
        raise GithubError("GitHub responded 403 … API rate limit exceeded", status=403)

    client = GithubClient("someone", "headsize-studio", fetch=boom)
    report = verify_release.verify(SLUG, TAG, client=client)

    assert not report.ok
    assert "GITHUB_TOKEN" in report.findings[0].detail
    assert "API rate limit" in report.findings[0].detail


def test_the_token_can_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    assert verify_release.token_from_environment() == ""
    monkeypatch.setenv("GH_TOKEN", "gh-token")
    assert verify_release.token_from_environment() == "gh-token"
    monkeypatch.setenv("GITHUB_TOKEN", "gh-preferred")
    assert verify_release.token_from_environment() == "gh-preferred"


def test_the_report_renders_and_serialises() -> None:
    report = run_verify(release_json())
    rendered = report.render()

    assert "all checks passed" in rendered
    payload = report.as_json()
    assert payload["ok"] is True
    assert payload["tag"] == TAG
    assert len(payload["findings"]) == len(report.findings)
