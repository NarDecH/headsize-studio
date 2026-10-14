"""Build the portable Windows executable and its checksum file.

Run:  python tools/build_exe.py [--skip-self-test]

Output:

* ``dist/HeadSize-Studio-<version>-windows-x64.exe``
* ``dist/SHA256SUMS.txt``

The release workflow uploads exactly those two files, which is what the in-app
updater looks for.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from headsize.version import APP_NAME, __version__  # noqa: E402

SPEC = ROOT / "packaging" / "headsize.spec"


def platform_tag() -> str:
    machine = (platform.machine() or "x64").lower()
    arch = {"amd64": "x64", "x86_64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(
        machine, machine
    )
    if os.name == "nt":
        return f"windows-{arch}"
    if sys.platform == "darwin":
        return f"macos-{arch}"
    return f"linux-{arch}"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def run_self_test(exe: Path) -> tuple[bool, str]:
    """Launch the built executable's self-test and read its report."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONUTF8="1")
    report = Path(os.environ.get("APPDATA", Path.home())) / "HeadSizeStudio" / "logs" / "self-test.txt"
    if report.exists():
        report.unlink()
    started = time.time()
    process = subprocess.run(  # noqa: S603 - our own build
        [str(exe), "--self-test"],
        env=env,
        capture_output=True,
        timeout=600,
        check=False,
    )
    elapsed = time.time() - started
    text = ""
    if report.exists():
        text = report.read_text(encoding="utf-8", errors="replace")
    if process.returncode != 0:
        stdout = process.stdout.decode("utf-8", "replace")[-2000:]
        return False, f"exit code {process.returncode}\n{stdout}\n{text}"
    return True, f"{elapsed:.1f}s\n{text.strip()}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the portable executable")
    parser.add_argument("--skip-self-test", action="store_true")
    parser.add_argument("--keep-spec-output", action="store_true")
    args = parser.parse_args(argv)

    tag = platform_tag()
    print(f"Building {APP_NAME} {__version__} for {tag}")

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is missing: pip install -r requirements-dev.txt", file=sys.stderr)
        return 2

    dist = ROOT / "dist"
    work = ROOT / "build"
    for folder in (dist, work):
        if folder.exists():
            shutil.rmtree(folder)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(SPEC),
        "--noconfirm",
        "--clean",
        "--distpath",
        str(dist),
        "--workpath",
        str(work / "pyinstaller"),
        "--log-level",
        "WARN",
    ]
    print(" ".join(command))
    result = subprocess.run(command, cwd=ROOT, check=False)  # noqa: S603
    if result.returncode != 0:
        print("PyInstaller failed", file=sys.stderr)
        return result.returncode

    suffix = ".exe" if os.name == "nt" else ""
    built = dist / f"HeadSize-Studio{suffix}"
    if not built.is_file():
        candidates = [p for p in dist.iterdir() if p.suffix == suffix]
        if not candidates:
            print("could not find the built executable", file=sys.stderr)
            return 3
        built = candidates[0]

    artifact = dist / f"HeadSize-Studio-{__version__}-{tag}{suffix}"
    if artifact.exists():
        artifact.unlink()
    built.rename(artifact)
    size_mb = artifact.stat().st_size / 1024 / 1024
    print(f"built {artifact.name} ({size_mb:.1f} MiB)")

    digest = sha256_of(artifact)
    checksums = dist / "SHA256SUMS.txt"
    checksums.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
    print(f"sha256 {digest}")

    if not args.skip_self_test and os.name == "nt":
        ok, detail = run_self_test(artifact)
        print(detail)
        if not ok:
            print("the built executable failed its self-test", file=sys.stderr)
            return 4
        print("packaged self-test passed")

    if not args.keep_spec_output:
        shutil.rmtree(work / "pyinstaller", ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
