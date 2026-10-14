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
    assert (ROOT / "docs" / "changelog.md").is_file()
    assert "tools/make_release_notes.py" in text, (
        "the body must be converted so its relative links resolve on the page"
    )
    assert "body_path: release-notes.md" in text
    assert "body_path: docs/changelog.md" not in text, (
        "the raw changelog links point at files that do not exist on a Release page"
    )
    assert "generate_release_notes: true" not in text, (
        "generated notes replace body_path, so the changelog would be lost"
    )


def test_release_uploads_the_assets_the_updater_downloads() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert "dist/HeadSize-Studio-*.exe" in text, "the updater needs a matching .exe asset"
    assert "dist/SHA256SUMS.txt" in text, "the updater verifies against SHA256SUMS.txt"


def test_release_notes_are_built_for_the_tag_being_released() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    notes_step = text.split("tools/make_release_notes.py", 1)[1]
    assert "--ref" in notes_step, "the links must be pinned to the released tag"


def test_the_published_release_is_verified_after_publishing() -> None:
    text = RELEASE.read_text(encoding="utf-8")
    assert "tools/verify_release.py" in text, "every release must be checked after it is live"
    assert "--download --self-test" in text, "checking the published binary is the whole point"
    assert "needs: [publish" in text, "verification must follow the publish job"


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
