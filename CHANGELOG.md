# Changelog

## 0.5.0 — 2026-10-21 — preview

- Make `Install.cmd` install the plugin, extra-format converter, private Python and AI dependencies in one workflow, with a final setup summary and logs.
- Bootstrap checksum-verified CPython 3.12.15 when needed. Retain a working existing Python 3.10–3.12 environment; leave system PATH and Cinema 4D's Python unchanged. No administrator rights are required.
- Check NVIDIA GPU/driver prerequisites before large AI downloads. Preserve the installed plugin and completed converter setup if AI setup fails.
- Reuse ready components on repeated setup; provide AI repair, import-only and core-only modes. The in-plugin setup button uses the same Python bootstrap.
- Preserve the working converter during failed repair; recover from corrupt Python/PyTorch downloads and report partial setup accurately.
- Validate a fresh Python 3.12 environment with actual image generation and run 112 portable regression tests.
- Update English/Russian installation guides and third-party runtime notices.
- Recheck native C4D behaviour: 12 camera/light changes, six render evaluation contexts and a MoGraph Fracture rig across 13 frames. Surface-card geometry remained intact; these are bounded regression checks, not a universal no-crash or real-time performance guarantee. See [validation scope](docs/validation.md).

## 0.4.0 — 2026-10-21

- Load SCAN data, evaluate colour and prepare geometry in a cancellable background worker. Conversion, reading and C4D assembly now have progress and elapsed time; Status remains in Attributes.
- Build C4D cards and update their attributes in small UI-thread batches. Keep the previous complete model visible until its replacement is ready.
- Cancel through the progress window, its close button or Cancel Processing. Failed/cancelled requests do not retry until the input/settings change or Initialise / Reload is clicked.
- Read binary Gaussian PLY and SPLAT without allocating discarded records. Validate the complete source, preserve deterministic sampling, and eliminate the second full validation pass after conversion.
- Reuse unchanged scans on Initialise / Reload. Separate camera-dependent SH colours from surface-card geometry and normal smoothing.
- Route Source Fidelity's opacity reload and camera-facing rebuild through the same cancellable pipeline.
- Debounce viewport changes for 0.3 seconds; discard obsolete work when parameters or camera change again. Offline render/export still evaluates the requested state synchronously.
- Preserve point-preview limits, full Redshift geometry, file formats, material controls and existing object IDs.
- Add regression coverage for cancellation, sampling parity, invalid records and camera/cache dependencies; 105 portable tests pass.

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
