# Changelog

## 1.5.0 — 2026-11-24
- Larger, distance-independent display defaults matching native camera / locator references.
- Separate display-only camera/target sliders, numeric multipliers, halve/double/reset buttons.
- Preserve transforms, optical settings and animation; reject keyed/driven/locked display overrides.
- Normalize older tiny targets without recreating their rig; evaluate display bounds for picking.
- New keys explicitly follow current Maya tangent defaults; existing manual tangents stay intact.
- Add an opt-in, confirmed and undoable direct-curve tangent conversion; refuse shared/reference/custom drivers.
- 33 plain-Python checks, 18 new Maya 2023 feature checks and 24 existing GUI regressions passed.


## 1.4.1 — 2026-11-24
- Correct interactive creation order: mouse press anchors the target; dragging positions the camera.
- Keep the target fixed during preview updates; select the camera on release.
- Update tool help, menu annotations, button labels and usage documentation.
- Preserve existing camera transforms, targets and roll keys; do not reverse existing rigs.
- Add 10 callback unit checks and a native Maya 2023 pointer verification.
- Initial public GitHub release with bilingual documentation and original explanatory diagrams.

## 1.4.0 — 2026-11-24
- Add native drag creation and near-focus-plane placement.
- World-up horizon locking avoids unintentional roll during translation.
- Add explicit horizon repair preserving keyed/driven roll.
- Fix mixed MEL/Python menu callbacks.

## 1.3.0 — 2026-11-23
- Native local-Z roll, editable lens proxies and parameter panel.
- Smaller target display and independent display scale controls.
- Explicit legacy-rig upgrades with animation preservation safeguards.
