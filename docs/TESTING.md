# Validation scope / 验证范围

## Public reproducible tests

Run from the repository root with Python 3.9 or newer:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python tools/build_release.py
```

- `test_drag_direction.py`: 11 tests of target-first placement callbacks using fake Maya commands. Covers first and repeated drag, perspective/orthographic projection, release, cancel, zero distance, non-left input, and labels.
- `test_display_and_tangents.py`: 13 policy checks for display-only writes, legacy normalization, rollback/refusal safeguards, reading Maya defaults and preserving existing key tangents.
- `test_installer.py`: 5 filesystem tests against temporary directories. Checks existing startup/env preservation, managed backups, rejection of unowned module files/folders, and repeated disable/reinstall.
- `test_public_package.py`: 8 checks covering source syntax, archive allowlist and license, private-path/PNG metadata guards, consistent release versions, locked camera Scale, absence of experimental R hooks, and deterministic packaging.

**These are not Maya runtime tests.** The included opt-in CI example does not install or run Autodesk Maya. It is not enabled by default; copy `docs/ci-checks.example.yml` to `.github/workflows/checks.yml` to enable it with suitable repository permissions. The fake command layer cannot establish actual mouse behavior or DG evaluation.

## v1.5.1 maintenance validation

37 plain-Python checks pass. Runtime/installer entry points differ from v1.5.0 only in the two version constants; camera creation, display resizing, animation and installation behavior are unchanged. New checks lock in the documented scope: camera transform Scale stays locked, the unshipped R adapter is absent from runtime sources, release metadata is consistent, and repeated builds are byte-identical.

No additional Maya GUI verification was run for v1.5.1. The unpublished native-R prototype was discontinued after validation crashes, is excluded from the release, and is not a supported manual smoke test. The v1.5.0 GUI evidence below is historical, not a new certification of this maintenance release or any other Maya year.

## Manually verified in Maya 2023 on Windows

v1.5.0: 18 feature checks plus 24 existing GUI regressions in a separate desktop-launched blank validation process. Compared native camera/locator display defaults at multiple distances in cm/m/mm, and native animation values for Auto, Linear, Spline, Clamped, Flat and Step combinations with weighted/nonweighted curves. Verified unchanged transforms, focal/optical values, target distance, key times/values/tangents and transform Scale during display resizing, including auto-key enabled. Checked old small target reset, independent sliders, undo/redo, rejection of driven/keyed/locked displays and shared/custom animation curves. Confirmed new display attributes are non-keyable. Six runtime/installer entry points still pass Python 2.7 syntax parsing; only Maya 2023 has been runtime-tested.


v1.4.1: native mouse press/drag/release places the target at press and the camera at drag. On release the camera is selected, aims at its target and has zero Roll. Existing scene objects, camera/target transforms and keyframes were preserved. The temporary verification rig was removed after identity checks.

v1.4.0: 24 existing GUI regressions, 10 horizon/placement checks, 8 menu/window lifecycle checks, and installer tests were previously completed. These are historical validation counts, not extra checks executed by this public CI.

No other Maya year has been runtime-certified. World-up pole behavior remains a documented limitation.

## Manual smoke test for contributors

Use a disposable scene or a separate test window, not production data:

1. Install by dragging the installer file into a viewport; open the native camera submenu.
2. Press at point A and drag to B. The target must stay at A; the camera must end at B.
3. Continue dragging before release: only the camera position should change.
4. Release: the camera should be selected. Move it with W; the target must not translate.
5. Check zero Roll with no intentional roll input; test an oblique view away from the up-axis pole.
6. Set/key local Z roll, then translate; the roll/key values must remain user-controlled.
7. Close/reopen the panel and refresh the menu without duplicate entries or errors.
8. Save/reopen only the disposable test scene and verify that native-node following still works.

Do not publish production scenes, workstation logs or screenshots containing personal information.
