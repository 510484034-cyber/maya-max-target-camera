# Changelog

## 1.5.1 — 2026-11-24
- Stable maintenance release: retain the v1.5.0 camera creation, display-panel controls and Maya-default key tangents without changing runtime behavior.
- Confirm that experimental native-R camera display scaling is not included. An unpublished prototype was discontinued after crashes in validation; it was never part of a public release.
- Document the supported route: resize camera icons with the display panel, keep the camera transform Scale locked, and do not override Maya's R tool.
- Keep existing target operations; distinguish transform Scale from the panel's display-only controls.
- Refresh bilingual download/upgrade instructions and retain existing watermark-free artwork and search keywords.
- Add four release safeguards for consistent version metadata, locked camera scale, absence of experimental hooks and deterministic packaging: 37 plain-Python checks in total.
- Reuse the documented v1.5.0 Maya 2023 validation as historical evidence; no new Maya GUI test or additional Maya-year certification is claimed for this maintenance release.

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
