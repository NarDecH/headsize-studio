"""Auto-update built on GitHub Releases.

* :mod:`headsize.update.version`  — semantic version parsing/comparison
* :mod:`headsize.update.github`   — tiny, injectable GitHub Releases client
* :mod:`headsize.update.updater`  — check / download / verify orchestration
* :mod:`headsize.update.selfupdate` — replace the running executable

Nothing here imports Qt, so the whole flow is testable headlessly.
"""

from headsize.update.github import (
    GithubClient,
    GithubError,
    ReleaseAsset,
    ReleaseInfo,
)
from headsize.update.selfupdate import (
    apply_update,
    cleanup_leftovers,
    supports_self_update,
)
from headsize.update.updater import UpdateCheck, Updater
from headsize.update.version import compare_versions, is_newer, parse_version

__all__ = [
    "GithubClient",
    "GithubError",
    "ReleaseAsset",
    "ReleaseInfo",
    "UpdateCheck",
    "Updater",
    "apply_update",
    "cleanup_leftovers",
    "compare_versions",
    "is_newer",
    "parse_version",
    "supports_self_update",
]
