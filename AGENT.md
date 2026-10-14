# AGENT.md — working on HeadSize Studio

This is the orientation document for anyone (human or AI agent) changing this
repository. Read it before editing; it records the architecture, the rules that
must not be broken, and how to verify a change.

---

## 1. What the program is

A desktop app that resizes the head of people in a photo. It detects faces, then
applies a smooth elliptical "liquify" scale around each head. The user edits with
a live preview and exports the result.

**Stack:** Python 3.10+ · PyQt6 (GUI) · OpenCV 5 (DNN detection + `cv2.remap`) ·
NumPy · Pillow (image IO) · PyInstaller (portable Windows build) · no other
runtime dependency, no network access except the optional update check.

## 2. Layout

```
headsize/
  version.py            single source of truth for the version
  app.py                entry point: logging, theming, window (run())
  __main__.py           `python -m headsize`
  cli.py                `python -m headsize.cli` (batch, no Qt import)
  diagnostics.py        `--self-test`: 12 end-to-end checks, frozen-build safe
  core/                 THE ENGINE — must never import Qt
    types.py            HeadRegion, FaceDetection, scale bounds, default feather
    geometry.py         face box -> head ellipse (proportions + eye line)
    detector.py         YuNet wrapper, model resolution, download + SHA-256
    warp.py             the warp maths, ROI handling, cv2.remap
    pipeline.py         proxy helpers (preview, detection downscale)
    document.py         image + regions + undo history + preview cache
    io.py               Pillow load/save, EXIF orientation, ICC/DPI
    config.py           user settings JSON
    presets.py          head-size presets
  ui/                   PyQt6 (never imported by core)
    theme.py            palettes + the QSS template (@token substitution)
    icons.py            inline SVG icons -> QIcon
    widgets.py          Card, SliderRow, SegmentedControl, RegionRow, ...
    canvas.py           zoom/pan canvas, region handles, split compare
    sidebar.py          the whole control column
    dialogs.py          about, shortcuts, update, settings
    workers.py          thread-pool workers (never block the UI thread)
    main_window.py      actions, menus, toolbar, status bar, wiring
    i18n.py             Thai/English catalogue (pure Python)
  update/               GitHub Releases update flow (no Qt)
    version.py          semver parsing/comparison
    github.py           Releases API client (injectable fetch)
    updater.py          check -> pick asset -> download -> verify
    selfupdate.py       detached helper script that swaps the executable
    repo.py             owner/repo defaults (rewritten by tools/set_repo.py)
  assets/
    models/             YuNet ONNX (MIT) + its licence text
    icons/              generated app icon (tools/make_icon.py)
docs/                   readme/research/changelog in .md and .html + assets
tools/                  doc images, doc build, icon, exe build, helpers
tests/                  pytest suite (GUI tests run offscreen)
packaging/headsize.spec PyInstaller recipe
```

## 3. Invariants

Break one of these and the tests fail — that is deliberate.

1. **`headsize.core` never imports Qt.** The engine must stay usable from the CLI,
   from tests and in a scene without a display.
2. **`w = 0` at the ellipse rim and `w = 1` in the core.** Consequences that are
   asserted in `tests/test_warp.py`:
   - `scale == 1.0` returns the input bit-for-bit;
   - pixels outside the ellipse are never written;
   - the core is scaled by *exactly* `scale`.
3. **Only the destination ROIs are processed.** If you touch the remap code, keep
   the source-slice padding (`ceil(|1/s − 1| · r_max) + 2`) and the destination
   grid origin (`dx0`, `dy0`) distinct — mixing them up silently shifts the whole
   warp (this bug existed and was caught by `test_outside_ellipse_is_untouched`).
4. **The document is parametric.** Undo history stores `HeadRegion` copies, never
   pixels; exports always re-render from the original array.
5. **No `processEvents()` in loops, no blocking work on the UI thread.** Slow work
   goes through `ui/workers.py`.
6. **UI strings go through `t()`** and must exist in *both* languages
   (`tests/test_i18n.py` checks for missing keys).
7. **Plain `QWidget` subclasses that need a QSS background must call
   `setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)`** — otherwise they
   paint with the system palette and the dark theme looks broken.
8. **The version lives in `headsize/version.py`** and is mirrored in
   `pyproject.toml`; the release workflow refuses a mismatch.

## 4. How the warp works (read this before touching `warp.py`)

For each destination pixel `p` inside an elliptical zone: transform into the
ellipse frame, compute the normalised radius `d`, get the smoothstep weight
`w(d)`, shrink the sampling radius by `m = 1 + (1/s − 1)·w`, and read the source
pixel there. One `cv2.remap` per zone, cubic or bilinear.

Defaults and their reasons:

- `DEFAULT_PAD_X = 1.25`, `DEFAULT_PAD_Y = 1.22` — the zone must be bigger than
  the head, otherwise growth is capped (see `docs/research.md` §5).
- `DEFAULT_FEATHER = 0.22` — keeps the head outline inside the rigid core so the
  slider number matches what you see.
- Zone radii, angle and scale are in **full-resolution image coordinates**; the
  canvas converts, the document never scales.

## 5. Daily commands

```bash
python -m pytest                        # everything (GUI offscreen), ~40 s
python -m pytest -q tests/test_warp.py  # the guarantee tests
python -m headsize --self-test          # 12 end-to-end checks, works frozen
python -m headsize --verbose            # GUI with a log on stderr
python -m headsize.cli photo.jpg --scale 1.3
python tools/make_doc_images.py         # regenerate docs/assets
python tools/build_docs.py --check      # rebuild + validate the HTML docs
python tools/build_exe.py               # dist/HeadSize-Studio-<ver>-windows-x64.exe
python tools/make_release_notes.py --out release-notes.md --ref v1.0.0
python tools/verify_release.py --tag v1.0.0 --download --self-test   # live release
```

Set `HEADSIZE_TEST_IMAGE=/path/to/portrait.jpg` and run
`python -m pytest -m integration` to exercise the real-photo path (detection,
effective scale measurement). That test is skipped without the variable because
the repository refuses to ship third-party photographs.

## 6. Verifying a change

1. Run the full suite; do not skip or weaken an assertion to make it pass.
2. For anything touching the warp, re-check the `test_warp.py` guarantees *and*
   measure the effective scale (`-m integration`) — a change can look correct
   while shifting the ROI by a few pixels.
3. For UI changes, take a screenshot offscreen (`window.grab()`) and check it
   programmatically: the sidebar/canvas must not overlap, the render must not be
   flat (`tests/test_gui.py::test_screenshot_is_a_rich_render`). For a visual
   look, run `preview_open`/`register_preview` on `docs/readme.html` or run the
   app yourself.
4. For packaging changes, build the exe and run
   `dist/<exe> --self-test` — it must print `all 12 checks passed`.
5. Update `docs/changelog.md` (and the root `CHANGELOG.md`) for user-visible
   changes, then `python tools/build_docs.py` so the HTML matches.

## 7. Environment notes

- **OpenCV 5 removed the Haar cascades.** `cv2.CascadeClassifier` does not exist;
  use `cv2.FaceDetectorYN` (see `docs/research.md` §2 for the comparison).
- **Use `opencv-python-headless`.** The GUI is Qt; the OpenCV highgui build adds
  ~40 MB of unused Qt/DLLs to the bundle.
- **Detection is capped to a 1600 px proxy** (`DETECT_MAX_SIDE`) for speed.
- **Previews cap at 1400 px** (`PREVIEW_MAX_SIDE`); exports always use full
  resolution.
- **The app must run with `QT_QPA_PLATFORM=offscreen`** in tests and CI. Test
  modules set it before importing `QtWidgets`.
- **Thai text in console output:** `app.setup_logging()` reconfigures stderr to
  UTF-8 with `errors="replace"`, and tests run with `PYTHONUTF8=1`.

## 8. Releasing

1. Update `headsize/version.py` and `pyproject.toml` (same version).
2. Add a changelog entry in `docs/changelog.md` + `CHANGELOG.md`.
3. `python tools/build_docs.py` and commit the regenerated HTML.
4. Tag and push: `git tag v1.0.0 && git push origin main --tags`.
5. `.github/workflows/release.yml` tests on three platforms, builds the Windows
   executable, writes `SHA256SUMS.txt` and publishes the release. Running
   installations pick it up through the in-app updater.

6. Verify what actually went live: `python tools/verify_release.py --tag v1.0.0
   --download --self-test`. It needs no token (set `GITHUB_TOKEN` to avoid the
   anonymous 60 requests/hour limit) and reports each finding as `[ok]`/`[FAIL]`:
   the tag exists and is published, the updater picks a build for this platform
   and finds `SHA256SUMS.txt` listing it, the release is what a stable
   installation is offered, every link in the body resolves, the asset's digest
   matches the published checksum, and the downloaded build passes its own
   self-test. The Release workflow runs this automatically after publishing,
   because none of it can be checked from the source tree.

The release body is the changelog, converted by `tools/make_release_notes.py` so
its relative links resolve on the release page (GitHub renders a body against the
repository root, where `assets/…` does not exist). Never enable
`generate_release_notes`: GitHub's generated notes silently replace `body_path`.
To repair the notes of an existing release, run the Release workflow by hand with
its `tag` input set to that tag — the publish job updates the body in place.

The updater reads `headsize/update/repo.py`; `tools/set_repo.py --owner <name>`
rewrites it (plus the URLs in `pyproject.toml` and the docs) when the project is
published under a different account.

## 9. Style

- Type hints everywhere, `from __future__ import annotations`.
- Docstrings explain *why*; the maths gets its reasoning in the module docstring.
- Keep functions small; the engine is pure and side-effect free where possible.
- 96-column lines (`[tool.ruff]` in `pyproject.toml`), 4-space indent, line
  comments in English.
- Comments and code in English; the UI strings live in `ui/i18n.py` (Thai is the
  default language, English is the fallback for every key).
