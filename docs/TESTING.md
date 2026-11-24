# Validation scope / 验证范围

## Public reproducible tests

Run from the repository root with Python 3.9 or newer:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
python tools/build_release.py
```

- `test_drag_direction.py`: 10 tests of target-first placement callbacks using fake Maya commands. Covers first and repeated drag, perspective/orthographic projection, release, cancel, zero distance, non-left input, and labels.
- `test_installer.py`: 5 filesystem tests against temporary directories. Checks existing startup/env preservation, managed backups, rejection of unowned module files/folders, and repeated disable/reinstall.
- `test_public_package.py`: source syntax, archive allowlist, license inclusion, and no workstation paths in public text.

**These are not Maya runtime tests.** The included opt-in CI example does not install or run Autodesk Maya. It is not enabled by default; copy `docs/ci-checks.example.yml` to `.github/workflows/checks.yml` to enable it with suitable repository permissions. The fake command layer cannot establish actual mouse behavior or DG evaluation.

## Manually verified in Maya 2023 on Windows

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
