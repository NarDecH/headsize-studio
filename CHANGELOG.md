# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
this project adheres to [semantic versioning](https://semver.org/).

An illustrated version of this file, with screenshots, lives in
[docs/changelog.md](docs/changelog.md).

## [1.0.0] — 2026-10-14

First public release.

### Added
- Automatic face detection with the bundled YuNet DNN model (box + 5 landmarks).
- Elliptical radial warp to resize a head from 0.30× to 3.00× with a smooth,
  C¹-continuous falloff that leaves everything outside the influence zone
  bit-identical.
- Head geometry estimation from face proportions (centred on the eye line, sized
  from the box, padded for hair, tilted with the eyes).
- Multiple independently controlled heads per photo.
- PyQt6 GUI: zoom/pan canvas, drag handles for the zone, split compare, undo/redo,
  live preview, dark/light themes, Thai/English interface.
- Metadata-preserving export (EXIF, ICC, DPI) to PNG/JPEG/WebP/TIFF/BMP, with
  non-destructive default file names.
- Command line interface for batch work (`python -m headsize.cli`).
- Auto-update from GitHub Releases with SHA-256 verification and a detached
  self-replacing helper for portable builds.
- 132 automated tests, GitHub Actions CI and a tagged release workflow.
- Documentation: illustrated README, technical research notes and changelog, in
  both Markdown and HTML (`docs/`), plus AGENT.md for contributors.

### Known limitations
- Head growth saturates at roughly `1 / (head radius ÷ zone radius)` (≈1.4× with
  the default zone); enlarge the zone for extreme caricatures.
- Hard profile faces often need a manually placed zone.
- Self-update requires a packaged build.

[1.0.0]: https://github.com/HEADSiZE-OWNER/headsize-studio/releases/tag/v1.0.0
