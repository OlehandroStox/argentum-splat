# Changelog

## 0.7.0 — Automatic first view and source diagnostics

- Add Auto Frame in Empty Scene, enabled for new objects. Fit small/large source bounds with size-relative near clipping, output-aspect support, robust floater handling and matching AI source-camera metadata.
- Preserve user cameras, projection overrides, hand-edited generated cameras and existing scene content. Save the once-per-source marker and editable camera link with the document.
- Add Frame Loaded Scan for an explicit separate overview and Source Summary for counts, SH, colour-space, filtering and sampling information.
- Analyse at most 8,192 records in the background. Prepare the final view from the same parsed cloud, avoiding geometry preparation for a camera that is about to change. Reuse the analysis on LOOK/camera updates.
- Preserve the 0.6.2 projection fixes, quality defaults, automatic Redshift preparation, progress/cancellation and cache reuse.
- Add cross-scale/aspect, off-origin, floater, flat-scan, camera ownership, analysis reuse and graceful framing-failure regression tests.
- The fitted overview does not infer arbitrary scan orientation, physical units or website camera/post effects. The 3-million default import cap and Redshift card-renderer approximation remain.

## 0.6.2 — Large-scene projection and automatic render preparation

- Collapse behind-camera and out-of-frame projected cards instead of falling back to tilted geometry. Cap projected support to prevent near-camera background splats from stretching through city scans. Source records and per-splat indices remain intact.
- Keep perspective covariance and camera invalidation active at Pixel Footprint 0; zero now disables only the low-pass filter.
- Add Auto Prepare Redshift on Import, enabled for new objects. Set depth/sampling floors once per new source; preserve stricter settings, subsequent manual edits and the saved preparation marker. Include render settings and marker in one undo step.
- Skip redundant spatial normal smoothing for image-plane cards. Surface-aligned cards keep their existing smoothing behavior.
- Add regressions for near-eye-plane splats, bounded support, frustum-edge overlap, source-index preservation, zero-filter camera changes and once-per-source render preparation.
- Camera-facing geometry is specific to one view; use surface-aligned cards for secondary views or MoGraph movement across frame boundaries. A source SOG does not supply website camera/background settings.

## 0.6.1 — Source fidelity for every new object

- New objects start at the full 3,000,000 import cap and a 1/255 opacity threshold instead of 262,144 and 0.02. Dense scans no longer require a manual detail-preset step to avoid aggressive initial sampling.
- Default to Emission 1 / Diffuse 0 / Subsurface 0, full available SH, camera-facing covariance, Pixel Footprint 0.075 and zero normal-smoothing passes. sRGB decoding and neutral colour correction remain the starting colour pipeline.
- Share one quality profile between object creation and the explicit Source Fidelity action; new-material fallback weights agree with it. Attribute Manager reset defaults also agree with object creation.
- Preserve saved and cloned object values, material links and artistic settings. Existing objects adopt the profile only when Source Fidelity is explicitly applied. Render settings remain an explicit separate action.
- Keep the 10,000-point editor preview and the independent AI Gaussian Count choices. Larger retained scans need more memory/preparation time; camera-facing mode still recalculates geometry for real view changes.
- Add regression coverage for a 262,145-record faint scan, clone preservation, preset compatibility and material fallback weights.


## 0.6.0 — Quiet updates and scan detail

- Camera-only movement no longer cancels/restarts the source read or opens the processing dialog. Automatic LOOK/view updates run quietly after a settling interval; initial loads and explicit reloads keep progress and Cancel.
- Finish an in-flight camera request, publish it under its actual camera, then coalesce to the latest camera. The previous complete model remains available throughout.
- Tolerate camera-matrix round-trip noise in view cache keys, including render document copies; actual geometry and colour calculations retain full precision. Real camera, lens and output changes still invalidate the cache.
- Canonical SH keys avoid colour work for SH0, zero strength, zero-padded SH and equivalent requested degrees. Geometry and colour are reused independently by render document copies.
- Render copies reuse loaded scans even after global-cache eviction. Native binary Gaussian PLY loads retain packed source records when Maximum Splats exceeds 262,144; cancellation drops traceback references to abandoned allocations.
- Native preparation uses compact float64 buffers for positions, axes, normals and colours. Separate fixtures measured about 88% less retained Python source-cloud memory and 82.8% less retained prepared-buffer memory; these are component savings, not a promise for the whole Cinema 4D process.
- Batch colour correction skips neutral HSV work; measured 262,144-splat passes are about 2.9x faster for SH0 and 1.7x for SH3 on the tested machine, without NumPy.
- Add optional perspective screen-space covariance filtering (`Pixel Footprint`); preserve the prior card path at zero.
- Raise the Maximum Splats cap to 3,000,000. Source Fidelity enables that limit, SH3 / SH Strength 1, emission-only captured colour, opacity threshold at most 1/255, no normal smoothing, and 0.075 pixel-squared filtering. Status shows the retained/source percentage.
- Correct the source-fidelity footprint for actual pixel coordinates, avoiding oversized tiny bright splats. Pixel Footprint increments by 0.025; other LOOK sliders keep their 0.1 steps.
- Explain projection/render-camera mismatches in Status without changing explicit camera links. Rename the colour mode to sRGB Source to Scene Linear; correct decoding does not imply identical renderer compositing.
- Redshift Detail Quality disables Automatic Sampling and applies an adaptive error threshold of at most 0.01 so its manual sample floors take effect. Stricter existing values are preserved.
- Version the emission shader entry name when upgrading the exact legacy source; preserve manually edited shader code.
- The tested Raspberry scan has approximately 2.37 million source splats; all 2,309,943 passing the 1/255 opacity threshold fit under the new cap (97.4% of the source, no reservoir sampling). The remainder is opacity-filtered. Scans with more than 3 million eligible splats still use a deterministic sample.
- 187 portable tests pass on Python 3.10 and 3.12. Redshift cards remain an approximation and cannot promise pixel-identical native Gaussian output.


## 0.5.1 — License notices and distribution scope

- Preserve the TripoSplat-Training camera-reference and tqdm notices.
- Document actual converter license texts where npm metadata differs.
- Add dependency inventory snapshots and a repeatable metadata/notice reporter.
- Explain DINOv3, native-runtime and voluntary-support terms before setup downloads.
- No rendering, geometry or AI-generation behavior changed.


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
