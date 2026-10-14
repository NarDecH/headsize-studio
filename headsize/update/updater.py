"""Update orchestration: detect a release, verify it, download it."""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from headsize.update.github import (
    GithubClient,
    GithubError,
    ReleaseAsset,
    ReleaseInfo,
    USER_AGENT,
)
from headsize.update.version import is_newer, parse_version

CHECKSUM_ASSET_NAMES = ("sha256sums.txt", "sha256sums", "checksums.txt", "sha256.txt")
DOWNLOAD_CHUNK = 128 * 1024

ProgressCallback = Callable[[int, int], None]


@dataclass
class UpdateCheck:
    """Outcome of an update check, ready for display in the UI."""

    status: str  # "available" | "up-to-date" | "error" | "disabled"
    current: str
    latest: str = ""
    release: ReleaseInfo | None = None
    message: str = ""

    @property
    def available(self) -> bool:
        return self.status == "available"

    @property
    def notes(self) -> str:
        return self.release.notes if self.release else ""

    @property
    def url(self) -> str:
        return self.release.html_url if self.release else ""


@dataclass
class DownloadedUpdate:
    """A verified (or explicitly unverified) update payload on disk."""

    path: Path
    version: str
    asset_name: str
    sha256: str = ""
    verified: bool = False
    release_url: str = ""
    size: int = 0

    @property
    def warning(self) -> str:
        if self.verified:
            return ""
        return "Downloaded without a checksum file (SHA256SUMS.txt missing)."


def platform_key() -> str:
    if os.name == "nt" or sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def arch_key(machine: str | None = None) -> str:
    text = (machine or platform.machine() or "").lower()
    if text in ("x86_64", "amd64", "x64"):
        return "x64"
    if text in ("arm64", "aarch64"):
        return "arm64"
    if text in ("x86", "i386", "i686", "386"):
        return "x86"
    return text or "x64"


def executable_suffix() -> str:
    return ".exe" if platform_key() == "windows" else ""


class UpdateError(RuntimeError):
    pass


def parse_checksums(text: str) -> dict[str, str]:
    """Parse a ``sha256sum`` style file into ``{filename: digest}``."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([0-9a-fA-F]{64})\s+[* ]?(.+)$", line)
        if match:
            result[match.group(2).strip()] = match.group(1).lower()
    return result


def sha256_of(path: str | Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def rank_asset(asset: ReleaseAsset, platform_name: str, arch: str) -> int:
    """Higher is better; ``-1`` means "not for this platform"."""
    name = asset.name.lower()
    if any(token in name for token in ("sha256", "checksum", ".sig", ".json")):
        return -1
    if not name.endswith((".exe", ".zip", ".tar.gz", ".tgz", ".dmg", ".appimage")):
        return -1
    score = 0
    if platform_name == "windows":
        if not name.endswith(".exe"):
            return -1
        score += 4
    elif platform_name == "macos":
        if name.endswith((".dmg", ".app")):
            score += 4
        elif name.endswith((".zip", ".tar.gz")):
            score += 2
        else:
            return -1
    else:
        if name.endswith(".appimage"):
            score += 4
        elif name.endswith((".tar.gz", ".tgz", ".zip")):
            score += 2
        else:
            return -1
    for token, bonus in ((arch, 3), ("universal", 2), ("x64", 1), ("amd64", 1)):
        if token in name:
            score += bonus
            break
    if "portable" in name:
        score += 1
    if "setup" in name or "installer" in name:
        score -= 2  # prefer the portable build: it can self-update
    return score


def pick_asset(release: ReleaseInfo, platform_name: str | None = None, arch: str | None = None):
    """Best asset for this platform/arch, or ``None``."""
    plat = platform_name or platform_key()
    architecture = arch or arch_key()
    scored = [(rank_asset(a, plat, architecture), a) for a in release.assets]
    usable = [(s, a) for s, a in scored if s >= 0]
    if not usable:
        return None
    usable.sort(key=lambda item: (item[0], item[1].size), reverse=True)
    return usable[0][1]


def pick_checksum_asset(release: ReleaseInfo) -> ReleaseAsset | None:
    return release.find_asset(lambda a: a.name.lower() in CHECKSUM_ASSET_NAMES)


class Updater:
    """Check GitHub Releases and stage an update for the running platform."""

    def __init__(
        self,
        owner: str,
        repo: str,
        current_version: str,
        *,
        channel: str = "stable",
        client: GithubClient | None = None,
        opener: Callable[..., object] | None = None,
        platform_name: str | None = None,
        arch: str | None = None,
        workspace: Path | None = None,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.current_version = str(current_version)
        self.channel = channel
        self.platform_name = platform_name or platform_key()
        self.arch = arch or arch_key()
        self.workspace = Path(workspace) if workspace else None
        self._opener = opener or urllib.request.urlopen
        self.client = client or GithubClient(owner, repo)

    # ------------------------------------------------------------------ check
    def check(self) -> UpdateCheck:
        """Never raises: failures come back as ``status="error"``."""
        if not self.client.configured:
            return UpdateCheck(
                status="disabled",
                current=self.current_version,
                message="No update repository configured.",
            )
        try:
            release = self.client.latest_release(channel=self.channel)
        except GithubError as exc:
            return UpdateCheck(
                status="error", current=self.current_version, message=str(exc)
            )
        except Exception as exc:  # pragma: no cover - unexpected transport failure
            return UpdateCheck(
                status="error",
                current=self.current_version,
                message=f"Update check failed: {exc}",
            )

        if release is None:
            return UpdateCheck(
                status="up-to-date",
                current=self.current_version,
                message="No published releases yet.",
            )
        if not is_newer(release.version, self.current_version):
            return UpdateCheck(
                status="up-to-date",
                current=self.current_version,
                latest=release.version,
                release=release,
            )
        return UpdateCheck(
            status="available",
            current=self.current_version,
            latest=release.version,
            release=release,
            message=f"Version {release.version} is available.",
        )

    def asset_for(self, release: ReleaseInfo) -> ReleaseAsset | None:
        return pick_asset(release, self.platform_name, self.arch)

    # --------------------------------------------------------------- download
    def download(
        self,
        release: ReleaseInfo,
        *,
        destination: Path | None = None,
        progress: ProgressCallback | None = None,
        require_checksum: bool = False,
    ) -> DownloadedUpdate:
        """Download and checksum-verify the release asset for this platform."""
        asset = self.asset_for(release)
        if asset is None:
            raise UpdateError(
                f"No {self.platform_name}/{self.arch} build in release {release.version}."
            )
        target_dir = Path(destination) if destination else self._workspace_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / asset.name

        expected = self._expected_digest(release, asset)
        if require_checksum and not expected:
            raise UpdateError(
                "This release has no SHA256SUMS.txt, so the download cannot be verified."
            )

        temp = target.with_suffix(target.suffix + ".download")
        self._stream(asset.url, temp, progress)
        digest = sha256_of(temp)
        if expected and digest != expected:
            temp.unlink(missing_ok=True)
            raise UpdateError(
                f"Checksum mismatch for {asset.name}: expected {expected}, got {digest}."
            )
        os.replace(temp, target)
        return DownloadedUpdate(
            path=target,
            version=release.version,
            asset_name=asset.name,
            sha256=digest,
            verified=bool(expected),
            release_url=release.html_url,
            size=target.stat().st_size,
        )

    def download_and_apply(
        self,
        release: ReleaseInfo,
        *,
        progress: ProgressCallback | None = None,
    ) -> DownloadedUpdate:
        """Download, verify, then hand the payload to the self-updater."""
        from headsize.update.selfupdate import apply_update, supports_self_update

        if not supports_self_update():
            raise UpdateError(
                "Self-update is only available in packaged builds; "
                "download the release manually instead."
            )
        payload = self.download(release, progress=progress, require_checksum=False)
        apply_update(payload.path)
        return payload

    # ---------------------------------------------------------------- helpers
    def _workspace_dir(self) -> Path:
        if self.workspace is not None:
            return self.workspace
        from headsize.update.selfupdate import update_workspace

        return update_workspace()

    def _expected_digest(self, release: ReleaseInfo, asset: ReleaseAsset) -> str:
        checksum_asset = pick_checksum_asset(release)
        if checksum_asset is None:
            return ""
        try:
            text = self._fetch_text(checksum_asset.url)
        except (GithubError, urllib.error.URLError, OSError):
            return ""
        except Exception:  # pragma: no cover - defensive
            return ""
        table = parse_checksums(text)
        if not table:
            return ""
        digest = table.get(asset.name)
        if digest:
            return digest
        # Fall back to a single-entry file or a `*` prefixed name.
        for name, value in table.items():
            if name.lstrip("*") == asset.name:
                return value
        if len(table) == 1:
            return next(iter(table.values()))
        return ""

    def _stream(self, url: str, target: Path, progress: ProgressCallback | None) -> None:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self._opener(request, timeout=60) as response:  # type: ignore[call-arg]
                total = int(response.headers.get("Content-Length") or 0)
                done = 0
                with open(target, "wb") as handle:
                    while True:
                        chunk = response.read(DOWNLOAD_CHUNK)
                        if not chunk:
                            break
                        handle.write(chunk)
                        done += len(chunk)
                        if progress:
                            progress(done, total)
        except urllib.error.HTTPError as exc:
            target.unlink(missing_ok=True)
            raise UpdateError(f"Download failed with HTTP {exc.code}.") from exc
        except urllib.error.URLError as exc:
            target.unlink(missing_ok=True)
            raise UpdateError(f"Download failed: {exc.reason}") from exc
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise UpdateError(f"Download failed: {exc}") from exc
        if not target.exists() or target.stat().st_size == 0:
            raise UpdateError("Download produced an empty file.")

    def _fetch_text(self, url: str) -> str:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with self._opener(request, timeout=30) as response:  # type: ignore[call-arg]
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, "replace")


def cleanup_workspace(directory: Path | None = None) -> int:
    """Delete staged downloads older than a day. Returns how many were removed."""
    import time

    target = Path(directory) if directory else None
    if target is None:
        from headsize.update.selfupdate import update_workspace

        target = update_workspace()
    if not target.is_dir():
        return 0
    removed = 0
    cutoff = time.time() - 86400
    for candidate in target.iterdir():
        try:
            if candidate.stat().st_mtime < cutoff:
                if candidate.is_dir():
                    shutil.rmtree(candidate, ignore_errors=True)
                else:
                    candidate.unlink()
                removed += 1
        except OSError:
            continue
    return removed


def disk_space_for(path: Path, size: int) -> bool:
    """True when ``path``'s filesystem has room for ``size`` more bytes."""
    try:
        usage = shutil.disk_usage(path if path.exists() else path.parent)
    except OSError:
        return True
    return usage.free > size * 1.2 + 16 * 1024 * 1024


def staged_temp_path(name: str) -> Path:
    fd, raw = tempfile.mkstemp(prefix="headsize-", suffix=f"-{name}")
    os.close(fd)
    path = Path(raw)
    path.unlink(missing_ok=True)
    return path


__all__ = [
    "CHECKSUM_ASSET_NAMES",
    "DownloadedUpdate",
    "UpdateCheck",
    "UpdateError",
    "Updater",
    "arch_key",
    "cleanup_workspace",
    "disk_space_for",
    "executable_suffix",
    "parse_checksums",
    "pick_asset",
    "pick_checksum_asset",
    "platform_key",
    "rank_asset",
    "sha256_of",
    "staged_temp_path",
]
