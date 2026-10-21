# Changelog

## 0.3.2 — 2026-10-21

- Open the one-time Boosty donation form directly from the plugin and GitHub support links.
- Streamline documentation and bundled instructions; preserve dependency credits and license notices.

## 0.3.1 — 2026-10-21

- Add a quiet **Support the author - Boosty** button below Status in the object's Attributes.
- Open the author's Boosty page in the default browser only on click. No reminders, automatic network requests, or changes to generation/rendering.

## 0.3.0 — 2026-10-21 — first public preview

- Unified Input File for images, ready-made splats and video.
- Exact selected-frame preview and generation for video, animated images and numbered sequences.
- Nonmodal progress window centred over the active viewport, with Cancel and elapsed time; Status stays in Attributes.
- Real-valued LOOK/colour controls use 0.1 increments, retaining precise existing values. Minimum Opacity uses 0.001.
- One Extensions entry; the existing toolbar command remains available in Customize Commands.
- PyAV video decoding in the separate AI runtime.
- 95 portable tests covering core logic, formats, frame selection, routing and progress handling.
- Public English/Russian guides, clean installer ZIP and attributed example media.

**Preview limitation:** permanent Maxon plugin IDs and scene migration remain pending. This release retains development IDs for compatibility with existing local scenes.

## 0.2.0 — local development release

- Reuse geometry for LOOK updates; separate weight and colour updates.
- Source Fidelity preset, explicit Redshift detail quality button, estimated source camera.
- Alpha Erosion control with a default of 0 for fine silhouettes.
- Disable SH controls for files without view-dependent coefficients.

## 0.1.1 — local development release

- Fix black Redshift IPR with Point Preview enabled: full geometry remains available to the renderer.

## 0.1.0 — local development release

- Initial Cinema 4D Gaussian object, importers, Redshift card material and local TripoSplat integration.
- Colour correction, SH evaluation, viewport points, deformer geometry and MoGraph Fracture creation.
