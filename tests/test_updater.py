"""Update flow: version gates, asset choice, checksums, self-update swap."""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from headsize.update.github import GithubClient, GithubError, ReleaseInfo
from headsize.update.selfupdate import (
    apply_update,
    build_helper_script,
    cleanup_leftovers,
    supports_self_update,
    write_helper_script,
)
from headsize.update.updater import (
    UpdateError,
    Updater,
    cleanup_workspace,
    parse_checksums,
    pick_asset,
    rank_asset,
    sha256_of,
)

PAYLOAD = b"FAKE-WINDOWS-BUILD" * 512


# --------------------------------------------------------------------- fakes
class FakeHeaders:
    def __init__(self, length: int, charset: str = "utf-8") -> None:
        self._length = length
        self._charset = charset

    def get(self, key, default=None):
        if key.lower() == "content-length":
            return str(self._length)
        return default

    def get_content_charset(self):
        return self._charset


class FakeResponse:
    def __init__(self, data: bytes) -> None:
        self._buffer = io.BytesIO(data)
        self.headers = FakeHeaders(len(data))

    def read(self, size: int = -1) -> bytes:
        return self._buffer.read(size)

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc) -> bool:
        return False


def make_assets(version: str, exe_bytes: bytes = PAYLOAD, checksums: bytes | None = None):
    exe = f"HeadSize-Studio-{version}-windows-x64.exe"
    assets = [
        {
            "name": exe,
            "browser_download_url": f"https://files.test/{exe}",
            "size": len(exe_bytes),
            "content_type": "application/octet-stream",
        },
        {
            "name": f"HeadSize-Studio-{version}-macos-arm64.dmg",
            "browser_download_url": f"https://files.test/mac-{version}.dmg",
            "size": 10,
        },
        {
            "name": f"HeadSize-Studio-{version}-linux-x64.AppImage",
            "browser_download_url": f"https://files.test/linux-{version}.AppImage",
            "size": 10,
        },
    ]
    if checksums is not None:
        assets.append(
            {
                "name": "SHA256SUMS.txt",
                "browser_download_url": "https://files.test/SHA256SUMS.txt",
                "size": len(checksums),
            }
        )
    return assets


def make_release(version="1.1.0", *, prerelease=False, assets=None, draft=False, checksums=None):
    return {
        "tag_name": f"v{version}",
        "name": f"HeadSize Studio {version}",
        "body": f"Release notes for {version}",
        "html_url": f"https://github.com/acme/headsize-studio/releases/tag/v{version}",
        "published_at": "2026-10-01T10:00:00Z",
        "prerelease": prerelease,
        "draft": draft,
        "assets": (
            assets
            if assets is not None
            else make_assets(version, checksums=checksums)
        ),
    }


def make_client(releases):
    return GithubClient("acme", "headsize-studio", fetch=lambda url: releases)


def make_updater(
    releases,
    *,
    current="1.0.0",
    channel="stable",
    payloads=None,
    platform_name="windows",
    arch="x64",
    workspace=None,
):
    return Updater(
        "acme",
        "headsize-studio",
        current,
        channel=channel,
        client=make_client(releases),
        opener=make_opener(payloads or {}),
        platform_name=platform_name,
        arch=arch,
        workspace=workspace,
    )


def make_opener(payloads: dict[str, bytes]):
    def opener(request, timeout=30):
        url = getattr(request, "full_url", request)
        if url not in payloads:
            raise GithubError(f"unexpected download: {url}")
        return FakeResponse(payloads[url])

    return opener


def checksum_text(name: str, data: bytes) -> bytes:
    return f"{hashlib.sha256(data).hexdigest()}  {name}\n".encode()


# --------------------------------------------------------------------- check
def test_check_reports_available_release() -> None:
    check = make_updater([make_release("1.1.0")]).check()
    assert check.status == "available"
    assert check.available is True
    assert check.latest == "1.1.0"
    assert check.notes.startswith("Release notes")
    assert check.url.endswith("/v1.1.0")


def test_check_reports_up_to_date() -> None:
    check = make_updater([make_release("1.0.0")], current="1.0.0").check()
    assert check.status == "up-to-date"
    assert not check.available


def test_check_ignores_older_releases() -> None:
    check = make_updater([make_release("0.9.0")], current="1.0.0").check()
    assert check.status == "up-to-date"


def test_stable_channel_skips_prereleases() -> None:
    releases = [make_release("1.1.0", prerelease=True), make_release("1.0.5")]
    stable = make_updater(releases).check()
    assert stable.latest == "1.0.5"
    beta = make_updater(releases, channel="beta").check()
    assert beta.latest == "1.1.0"


def test_check_picks_the_highest_version_not_the_first() -> None:
    releases = [make_release("1.0.2"), make_release("1.4.0"), make_release("1.1.0")]
    assert make_updater(releases).check().latest == "1.4.0"


def test_draft_and_assetless_releases_are_ignored() -> None:
    releases = [
        make_release("2.0.0", draft=True),
        make_release("1.9.0", assets=[]),
        make_release("1.1.0"),
    ]
    updater = make_updater(releases)
    assert updater.check().latest == "1.1.0"


def test_check_handles_network_error() -> None:
    def boom(url):
        raise GithubError("403 rate limited")

    updater = Updater(
        "acme",
        "headsize-studio",
        "1.0.0",
        client=GithubClient("acme", "headsize-studio", fetch=boom),
    )
    check = updater.check()
    assert check.status == "error"
    assert "rate limited" in check.message


def test_check_disabled_without_repository() -> None:
    updater = Updater("", "", "1.0.0")
    check = updater.check()
    assert check.status == "disabled"
    assert not check.available


def test_no_releases_at_all() -> None:
    assert make_updater([]).check().status == "up-to-date"


# --------------------------------------------------------------- asset picking
def test_asset_ranking_prefers_portable_exe() -> None:
    portable = type("A", (), {"name": "app-windows-x64-portable.exe"})()
    setup = type("A", (), {"name": "app-windows-x64-setup.exe"})()
    assert rank_asset(portable, "windows", "x64") > 0
    assert rank_asset(portable, "windows", "x64") > rank_asset(setup, "windows", "x64")


def test_asset_ranking_rejects_other_platforms() -> None:
    dmg = type("A", (), {"name": "app-macos-arm64.dmg"})()
    assert rank_asset(dmg, "windows", "x64") == -1
    assert rank_asset(dmg, "macos", "arm64") > 0
    sums = type("A", (), {"name": "SHA256SUMS.txt"})()
    assert rank_asset(sums, "windows", "x64") == -1


def test_pick_asset_matches_platform() -> None:
    release = ReleaseInfo.from_json(make_release("1.1.0"))
    windows = pick_asset(release, "windows", "x64")
    assert windows is not None and windows.name.endswith("windows-x64.exe")
    macos = pick_asset(release, "macos", "arm64")
    assert macos is not None and macos.name.endswith(".dmg")
    linux = pick_asset(release, "linux", "x64")
    assert linux is not None and linux.name.endswith(".AppImage")


def test_pick_asset_returns_none_when_missing() -> None:
    release = ReleaseInfo.from_json(
        make_release("1.1.0", assets=[{"name": "notes.txt", "browser_download_url": "u"}])
    )
    assert pick_asset(release, "windows", "x64") is None


# -------------------------------------------------------------------- download
def test_download_verifies_checksum(tmp_path) -> None:
    name = "HeadSize-Studio-1.1.0-windows-x64.exe"
    sums = checksum_text(name, PAYLOAD)
    release = ReleaseInfo.from_json(make_release("1.1.0", checksums=sums))
    updater = make_updater(
        [make_release("1.1.0", checksums=sums)],
        payloads={
            f"https://files.test/{name}": PAYLOAD,
            "https://files.test/SHA256SUMS.txt": sums,
        },
    )
    result = updater.download(release, destination=tmp_path)
    assert result.verified is True
    assert result.warning == ""
    assert result.path.read_bytes() == PAYLOAD
    assert result.sha256 == hashlib.sha256(PAYLOAD).hexdigest()
    assert result.version == "1.1.0"
    assert not list(tmp_path.glob("*.download"))


def test_download_rejects_a_tampered_payload(tmp_path) -> None:
    name = "HeadSize-Studio-1.1.0-windows-x64.exe"
    sums = checksum_text(name, b"the real build")
    release = ReleaseInfo.from_json(make_release("1.1.0", checksums=sums))
    updater = make_updater(
        [make_release("1.1.0", checksums=sums)],
        payloads={
            f"https://files.test/{name}": b"a tampered build",
            "https://files.test/SHA256SUMS.txt": sums,
        },
    )
    with pytest.raises(UpdateError) as info:
        updater.download(release, destination=tmp_path)
    assert "Checksum mismatch" in str(info.value)
    assert list(tmp_path.iterdir()) == []


def test_download_without_checksums_is_flagged(tmp_path) -> None:
    release = ReleaseInfo.from_json(make_release("1.1.0"))
    name = "HeadSize-Studio-1.1.0-windows-x64.exe"
    updater = make_updater(
        [make_release("1.1.0")],
        payloads={f"https://files.test/{name}": PAYLOAD},
    )
    result = updater.download(release, destination=tmp_path)
    assert result.verified is False
    assert "checksum" in result.warning.lower()


def test_download_can_require_checksums(tmp_path) -> None:
    release = ReleaseInfo.from_json(make_release("1.1.0"))
    updater = make_updater([make_release("1.1.0")])
    with pytest.raises(UpdateError):
        updater.download(release, destination=tmp_path, require_checksum=True)


def test_download_reports_missing_platform_build(tmp_path) -> None:
    release = ReleaseInfo.from_json(
        make_release("1.1.0", assets=[{"name": "a.dmg", "browser_download_url": "u"}])
    )
    updater = make_updater([make_release("1.1.0")], platform_name="windows")
    with pytest.raises(UpdateError) as info:
        updater.download(release, destination=tmp_path)
    assert "windows" in str(info.value)


def test_download_failure_cleans_up(tmp_path) -> None:
    release = ReleaseInfo.from_json(make_release("1.1.0"))
    updater = make_updater([make_release("1.1.0")])  # no payloads registered
    with pytest.raises(UpdateError):
        updater.download(release, destination=tmp_path, require_checksum=False)
    assert not list(tmp_path.glob("*"))


def test_download_progress_is_reported(tmp_path) -> None:
    name = "HeadSize-Studio-1.1.0-windows-x64.exe"
    release = ReleaseInfo.from_json(make_release("1.1.0"))
    updater = make_updater(
        [make_release("1.1.0")], payloads={f"https://files.test/{name}": PAYLOAD}
    )
    seen: list[tuple[int, int]] = []
    updater.download(release, destination=tmp_path, progress=lambda d, t: seen.append((d, t)))
    assert seen and seen[-1][0] == len(PAYLOAD)
    assert seen[-1][1] == len(PAYLOAD)


def test_parse_checksums_handles_formats() -> None:
    text = (
        "# comment\n"
        f"{'a' * 64}  file-one.exe\n"
        f"{'B' * 64} *file-two.exe\n"
        "\n"
        "not a checksum line\n"
    )
    table = parse_checksums(text)
    assert table["file-one.exe"] == "a" * 64
    assert table["file-two.exe"] == "b" * 64
    assert len(table) == 2


# ---------------------------------------------------------------- self update
def test_self_update_requires_a_frozen_build(tmp_path) -> None:
    assert supports_self_update() is False
    with pytest.raises(Exception):
        apply_update(tmp_path / "missing.exe")


def test_apply_update_rejects_empty_payload(tmp_path) -> None:
    payload = tmp_path / "new.exe"
    payload.write_bytes(b"")
    with pytest.raises(Exception):
        apply_update(payload, target=tmp_path / "app.exe")


def test_helper_script_contains_the_essentials() -> None:
    windows = build_helper_script(windows=True)
    assert "Get-Process" in windows and "%PID%" in windows
    assert "move /Y" in windows
    assert "goto :rollback" in windows
    posix = build_helper_script(windows=False)
    assert "kill -0" in posix and "mv -f" in posix


def test_write_helper_script_is_next_to_the_payload(tmp_path) -> None:
    payload = tmp_path / "HeadSize-Studio.exe"
    payload.write_bytes(b"payload")
    script = write_helper_script(payload)
    assert script.parent == tmp_path
    assert script.exists()
    assert script.name.endswith((".cmd", ".sh"))


def test_cleanup_leftovers_removes_backups(tmp_path, monkeypatch) -> None:
    target = tmp_path / "HeadSize-Studio.exe"
    target.write_bytes(b"app")
    (tmp_path / "HeadSize-Studio.exe.old").write_bytes(b"old")
    (tmp_path / "x.update.cmd").write_text("script")
    monkeypatch.setattr(
        "headsize.update.selfupdate.current_executable", lambda: target
    )
    removed = cleanup_leftovers()
    assert len(removed) == 2
    assert not (tmp_path / "HeadSize-Studio.exe.old").exists()
    assert target.exists()


def test_cleanup_workspace_removes_old_files(tmp_path) -> None:
    fresh = tmp_path / "fresh.exe"
    fresh.write_bytes(b"x")
    stale = tmp_path / "stale.exe"
    stale.write_bytes(b"x")
    old = time.time() - 3 * 86400
    os.utime(stale, (old, old))
    assert cleanup_workspace(tmp_path) == 1
    assert fresh.exists() and not stale.exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows shell swap")
def test_swap_actually_replaces_the_binary(tmp_path) -> None:
    """End-to-end: the helper script swaps the file and relaunches it."""
    target = tmp_path / "app.cmd"
    target.write_text("@echo off\r\necho old-build\r\n", encoding="utf-8")
    payload = tmp_path / "download-payload.cmd"
    payload_text = '@echo off\r\necho new-build>"%~dp0started.txt"\r\n'
    payload.write_text(payload_text, encoding="utf-8")

    dead_pid = subprocess.Popen([sys.executable, "-c", ""]).pid
    time.sleep(0.3)  # let it exit so the wait loop returns at once

    apply_update(payload, target=target, pid=dead_pid)

    deadline = time.time() + 30
    while time.time() < deadline:
        if target.read_text(encoding="utf-8") == payload_text:
            break
        time.sleep(0.2)
    assert "new-build" in target.read_text(encoding="utf-8"), "binary was not replaced"
    assert "old-build" not in target.read_text(encoding="utf-8")

    marker = tmp_path / "started.txt"
    while time.time() < deadline and not marker.exists():
        time.sleep(0.2)
    assert marker.exists(), "relaunched build did not run"
    assert "new-build" in marker.read_text(encoding="utf-8")
    assert not (tmp_path / "app.cmd.old").exists()
