"""Where this copy of the app looks for updates.

``DEFAULT_OWNER`` is rewritten by ``tools/set_repo.py`` when the project is
published. A user can also override the coordinates at runtime (Tools →
Updates) or through the environment, which is handy for forks and mirrors.
"""

from __future__ import annotations

import os

#: GitHub account that owns the release repository.
DEFAULT_OWNER = "NarDecH"
#: Repository name.
DEFAULT_REPO = "headsize-studio"

ENV_OWNER = "HEADSIZE_UPDATE_OWNER"
ENV_REPO = "HEADSIZE_UPDATE_REPO"


def resolve_repo(
    owner: str = "", repo: str = "", *, api_base: str = ""
) -> tuple[str, str]:
    """Config value wins, then environment, then the baked-in default."""
    final_owner = (owner or os.environ.get(ENV_OWNER) or DEFAULT_OWNER).strip()
    final_repo = (repo or os.environ.get(ENV_REPO) or DEFAULT_REPO).strip()
    return final_owner, final_repo


def repo_is_configured(owner: str = "", repo: str = "") -> bool:
    resolved_owner, resolved_repo = resolve_repo(owner, repo)
    return bool(
        resolved_owner
        and resolved_repo
        and not resolved_owner.startswith("HEADSIZE-OWNER")
        and "OWNER" not in resolved_owner.upper()
    )


def release_page(owner: str = "", repo: str = "") -> str:
    resolved_owner, resolved_repo = resolve_repo(owner, repo)
    return f"https://github.com/{resolved_owner}/{resolved_repo}/releases"


__all__ = [
    "DEFAULT_OWNER",
    "DEFAULT_REPO",
    "ENV_OWNER",
    "ENV_REPO",
    "release_page",
    "repo_is_configured",
    "resolve_repo",
]
