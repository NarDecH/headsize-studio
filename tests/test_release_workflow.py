"""The packaging contract the auto-updater depends on, checked in the workflow.

The in-app updater reads a release's assets (a ``.exe`` plus ``SHA256SUMS.txt``)
and shows the release body as the update notes. Both are produced by
``.github/workflows/release.yml``, and both have failed silently before:
``generate_release_notes: true`` replaces ``body_path``, which shipped a release
whose notes were a bare link instead of the changelog.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE = ROOT / ".github" / "workflows" / "release.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"


def test_release_runs_on_version_tags() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert re.search(r"tags:\s*\[\"v\*\"\]", text), "releases must be triggered by v* tags"
    assert "workflow_dispatch" in text, "a manual re-publish must stay possible"


def test_release_body_is_the_changelog() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert "body_path: docs/changelog.md" in text
    assert (ROOT / "docs" / "changelog.md").is_file()
    assert "generate_release_notes: true" not in text, (
        "generated notes replace body_path, so the changelog would be lost"
    )


def test_release_uploads_the_assets_the_updater_downloads() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert "dist/HeadSize-Studio-*.exe" in text, "the updater needs a matching .exe asset"
    assert "dist/SHA256SUMS.txt" in text, "the updater verifies against SHA256SUMS.txt"


def test_release_checks_the_tag_against_both_version_files() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert "headsize/version.py" in text
    assert "pyproject.toml" in text
    assert "does not match version" in text, "a mis-tagged release must fail loudly"


def test_tag_input_is_used_when_a_release_is_republished_by_hand() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert text.count("github.event.inputs.tag || github.ref_name") >= 2, (
        "the dispatch input must drive tag_name and the prerelease flag"
    )


def test_ci_workflow_still_builds_and_self_tests_the_executable() -> None:
    text = CI.read_text(encoding="utf-8")
    assert "tools/build_exe.py" in text
    assert "python -m pytest" in text
