"""Semantic version helpers (no third-party dependency).

Handles the tag shapes GitHub releases actually use: ``1.2.3``, ``v1.2.3``,
``v1.2.3-beta.4``, ``1.2.3+win64`` and short forms like ``1.2``.
"""

from __future__ import annotations

import re
from functools import total_ordering

_VERSION_RE = re.compile(
    r"^\s*v?(?P<num>\d+(?:[._]\d+)*)"
    r"(?:[-_.]?(?P<pre>alpha|beta|rc|pre|preview|dev|a|b|c)[-_.]?(?P<prenum>\d*))?"
    r"(?:\+(?P<build>[\w.]+))?\s*$",
    re.IGNORECASE,
)

_PRE_RANK = {
    "dev": -4,
    "a": -3,
    "alpha": -3,
    "b": -2,
    "beta": -2,
    "c": -1,
    "rc": -1,
    "pre": -1,
    "preview": -1,
}


@total_ordering
class Version:
    """A comparable version.

    A release sorts above any of its pre-releases (``1.0.0 > 1.0.0-rc1``) and
    missing trailing numbers are treated as zero (``1.2 == 1.2.0``).
    """

    __slots__ = ("raw", "parts", "prerelease", "prerelease_number", "build")

    def __init__(self, value: str | Version | tuple[int, ...]) -> None:
        if isinstance(value, Version):
            self.raw = value.raw
            self.parts = value.parts
            self.prerelease = value.prerelease
            self.prerelease_number = value.prerelease_number
            self.build = value.build
            return
        if isinstance(value, tuple):
            self.raw = ".".join(str(p) for p in value)
            self.parts = tuple(int(p) for p in value)
            self.prerelease = None
            self.prerelease_number = 0
            self.build = ""
            return

        raw = str(value).strip()
        match = _VERSION_RE.match(raw)
        if not match:
            self.raw = raw
            self.parts = (0,)
            self.prerelease = None
            self.prerelease_number = 0
            self.build = ""
            return

        numbers = re.split(r"[._]", match.group("num"))
        self.raw = raw
        self.parts = tuple(int(n) for n in numbers if n != "")
        pre = match.group("pre")
        self.prerelease = pre.lower() if pre else None
        prenum = match.group("prenum")
        self.prerelease_number = int(prenum) if prenum else 0
        self.build = match.group("build") or ""

    @property
    def valid(self) -> bool:
        return bool(self.parts) and _VERSION_RE.match(self.raw) is not None

    @property
    def is_prerelease(self) -> bool:
        return self.prerelease is not None

    @property
    def major(self) -> int:
        return self.parts[0] if self.parts else 0

    @property
    def minor(self) -> int:
        return self.parts[1] if len(self.parts) > 1 else 0

    @property
    def patch(self) -> int:
        return self.parts[2] if len(self.parts) > 2 else 0

    def _key(self) -> tuple:
        numbers = self.parts + (0,) * (3 - len(self.parts)) if len(self.parts) < 3 else self.parts
        rank = 0 if self.prerelease is None else _PRE_RANK.get(self.prerelease, -1)
        return (numbers, rank, self.prerelease_number)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, (Version, str)):
            return NotImplemented
        return self._key() == Version(other)._key()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, (Version, str)):
            return NotImplemented
        a, b = self._key(), Version(other)._key()
        if a[0] != b[0]:
            return a[0] < b[0]
        return (a[1], a[2]) < (b[1], b[2])

    def __hash__(self) -> int:
        return hash(self._key())

    def __str__(self) -> str:
        text = ".".join(str(p) for p in self.parts)
        if self.prerelease:
            text += f"-{self.prerelease}{self.prerelease_number or ''}"
        return text

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Version({self.raw!r})"

    def tuple(self, length: int = 3) -> tuple[int, ...]:
        padded = self.parts + (0,) * max(0, length - len(self.parts))
        return padded[:length]

    def canonical(self, length: int = 3) -> str:
        """Padded, tag-free form used for filenames and comparisons: ``1.2.0``."""
        text = ".".join(str(p) for p in self.tuple(length))
        if self.prerelease:
            text += f"-{self.prerelease}{self.prerelease_number or ''}"
        return text


def parse_version(value: str | Version | None) -> Version:
    """Parse anything version-like; unparsable input becomes ``0.0.0``."""
    if value is None:
        return Version("0.0.0")
    return value if isinstance(value, Version) else Version(str(value))


def normalize_tag(tag: str) -> str:
    """``"v1.2.3-beta.1"`` -> ``"1.2.3-beta1"`` (padded to three numbers)."""
    return parse_version(tag).canonical()


def compare_versions(a: str | Version, b: str | Version) -> int:
    """-1 when ``a < b``, 0 when equal, 1 when ``a > b``."""
    left, right = parse_version(a), parse_version(b)
    if left == right:
        return 0
    return -1 if left < right else 1


def is_newer(candidate: str | Version, current: str | Version) -> bool:
    """True when ``candidate`` is a strictly newer version than ``current``."""
    return parse_version(candidate) > parse_version(current)


__all__ = [
    "Version",
    "compare_versions",
    "is_newer",
    "normalize_tag",
    "parse_version",
]
