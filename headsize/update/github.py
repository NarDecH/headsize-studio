"""A minimal GitHub Releases client.

The HTTP layer is injectable (``fetch_json``) so the update flow can be tested
without a network, and so the app can swap in a proxy or a mirror later.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

DEFAULT_API_BASE = "https://api.github.com"
USER_AGENT = "HeadSizeStudio-Updater"


class GithubError(RuntimeError):
    """Raised for any transport or response problem."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class ReleaseAsset:
    name: str
    url: str
    size: int = 0
    content_type: str = ""
    download_count: int = 0

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ReleaseAsset:
        return cls(
            name=str(data.get("name", "")),
            url=str(data.get("browser_download_url") or data.get("url") or ""),
            size=int(data.get("size") or 0),
            content_type=str(data.get("content_type") or ""),
            download_count=int(data.get("download_count") or 0),
        )


@dataclass
class ReleaseInfo:
    tag: str
    version: str
    name: str = ""
    notes: str = ""
    html_url: str = ""
    published_at: str = ""
    prerelease: bool = False
    draft: bool = False
    assets: list[ReleaseAsset] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> ReleaseInfo:
        from headsize.update.version import normalize_tag

        tag = str(data.get("tag_name") or data.get("name") or "")
        return cls(
            tag=tag,
            version=normalize_tag(tag),
            name=str(data.get("name") or ""),
            notes=str(data.get("body") or ""),
            html_url=str(data.get("html_url") or ""),
            published_at=str(data.get("published_at") or data.get("created_at") or ""),
            prerelease=bool(data.get("prerelease")),
            draft=bool(data.get("draft")),
            assets=[ReleaseAsset.from_json(a) for a in data.get("assets") or []],
        )

    def asset_named(self, *names: str) -> ReleaseAsset | None:
        wanted = {n.lower() for n in names}
        for asset in self.assets:
            if asset.name.lower() in wanted:
                return asset
        return None

    def find_asset(self, predicate: Callable[[ReleaseAsset], bool]) -> ReleaseAsset | None:
        for asset in self.assets:
            if predicate(asset):
                return asset
        return None

    def assets_matching(self, suffixes: Sequence[str]) -> list[ReleaseAsset]:
        lowered = tuple(s.lower() for s in suffixes)
        return [a for a in self.assets if a.name.lower().endswith(lowered)]


def fetch_json(url: str, *, timeout: float = 20.0, token: str | None = None) -> Any:
    """Default JSON fetcher (``urllib``, no third-party dependency)."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:  # pragma: no cover - best effort only
            detail = ""
        raise GithubError(
            f"GitHub responded {exc.code} for {url}. {detail}".strip(),
            status=exc.code,
        ) from exc
    except urllib.error.URLError as exc:
        raise GithubError(f"Cannot reach GitHub ({exc.reason}).") from exc
    except (TimeoutError, OSError) as exc:
        raise GithubError(f"Network error: {exc}") from exc
    except ValueError as exc:
        raise GithubError(f"Malformed JSON from GitHub: {exc}") from exc


class GithubClient:
    """Read releases from one repository."""

    def __init__(
        self,
        owner: str,
        repo: str,
        *,
        api_base: str = DEFAULT_API_BASE,
        fetch: Callable[[str], Any] | None = None,
        token: str | None = None,
        per_page: int = 30,
    ) -> None:
        self.owner = owner.strip()
        self.repo = repo.strip()
        self.api_base = api_base.rstrip("/")
        self._fetch = fetch or (lambda url: fetch_json(url, token=token))
        self.per_page = int(per_page)

    @property
    def configured(self) -> bool:
        return bool(self.owner and self.repo)

    @property
    def slug(self) -> str:
        return f"{self.owner}/{self.repo}"

    def releases_url(self) -> str:
        return f"{self.api_base}/repos/{self.owner}/{self.repo}/releases?per_page={self.per_page}"

    def latest_url(self) -> str:
        return f"{self.api_base}/repos/{self.owner}/{self.repo}/releases/latest"

    # -------------------------------------------------------------- fetching
    def list_releases(self) -> list[ReleaseInfo]:
        if not self.configured:
            raise GithubError("No update repository configured.")
        payload = self._fetch(self.releases_url())
        if not isinstance(payload, list):
            raise GithubError("Unexpected response from GitHub (expected a list).")
        return [ReleaseInfo.from_json(item) for item in payload]

    def latest_release(self, *, channel: str = "stable") -> ReleaseInfo | None:
        """Highest version release in the channel (stable skips pre-releases)."""
        from headsize.update.version import Version

        candidates: Iterable[ReleaseInfo] = self.list_releases()
        if channel == "stable":
            candidates = [r for r in candidates if not r.prerelease]
        usable = [r for r in candidates if not r.draft and r.assets]
        if not usable:
            return None
        return max(usable, key=lambda r: Version(r.version))


__all__ = [
    "DEFAULT_API_BASE",
    "GithubClient",
    "GithubError",
    "ReleaseAsset",
    "ReleaseInfo",
    "USER_AGENT",
    "fetch_json",
]
