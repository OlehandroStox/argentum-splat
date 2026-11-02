# Changelog

## 0.9.2 — 2026-10-30

- Match Photos' Brush rasterization contract: classic exponential Gaussian kernel, full opacity-dependent support, 0.3 pixel variance at default settings and no MIP area compensation. Other scans retain the normalized viewer profile.
- Store the profile per mesh so scans using different kernels can share a Redshift material. Migrate only recognized built-in shaders; preserve custom OSL.
- Add Training Colour: Redshift Linear by default, or sRGB for conventional splat viewers. Calibration uses display images; linear training uses lossless 16-bit RGB PNG copies. Embed colour space and renderer profile in the exported PLY.
- Preserve source photo details through lossless preprocessing and honour embedded ICC profiles. Original files remain unchanged.
- Existing sRGB PLYs benefit from the kernel correction but need reconstruction in Linear mode to remove the colour-compositing mismatch.

## 0.9.1 — 2026-10-30

- Clarify Single Image (one AI-inferred view) versus Multi-Photo Scan (3–500 overlapping views); keep existing saved values.
- Compact Help tab: reader button at the top; remove the collapsing inline manual. Help Reader includes live status, author credit, GitHub and Boosty.
- Show the same lazy status in every plugin tab without issuing scene events that restart IPR.
- Clone render settings into `Argentum Splat - Splatting Transparency`; preserve the original preset and effects, support Undo, and reuse the owned copy.
- New multi-photo scans default to 30,000 training steps. Stop growth halfway through short runs (at most 15,000), leaving time for refinement.
- Save all calibrated capture views beside a multi-photo result; Captured View creates and activates the selected camera. Older results retain their single saved camera.
- A photo scan only reconstructs observed surfaces. Existing PLYs are not retrained by updating the plugin; arbitrary viewpoints and Redshift card compositing still have limits.

## 0.9.0 — 2026-10-29

- Separate Image, Photos and Scan tabs; version footer includes `with love Olehandro Stoxholm`.
- Photos reconstructs one scan from overlapping photographs using local PyCOLMAP and Brush, with a separate runtime, alignment diagnostics, cancellation and automatic import.
- Photos results retain a calibrated starting view and its aspect ratio for automatic framing. In an otherwise empty scene, the default ACES view switches once to Un-tone-mapped for captured colours; existing scenes and custom views are preserved.
- Removed moving-image/sequence decoding, related controls and PyAV dependency. Image uses one still picture.
- Preserved 0.8.3 scan caching and opacity compensation. Camera motion still requires view-dependent updates when applicable.


## 0.8.3 — Faster scan updates, subpixel filtering and custom AI counts

- Keep running-job progress out of serialized scene data and avoid scene/Attribute Manager events for progress ticks. Redshift no longer restarts IPR for every progress notification; completed geometry is published atomically. Camera-dependent projection still needs an update after camera motion, using the retained source.
- Reduce waiting between native assembly slices, with a short shared time budget across active jobs. Clarify camera-only status messages when visibility requires new card topology.
- Add 524,288 and 1,048,576 Image Gaussian Count presets plus Custom (32,768–1,048,576, multiples of 32). Values above 262,144 are experimental; preserve the numeric count in existing scenes.

- Accelerate validated packed PLY projection, SH colour, bounds and visible-card selection with optional NumPy. Keep bounded worker batches, cancellation checks and the ordinary Python fallback.
- Reuse decoded source components in a bounded cache and retain completed preparation stages when a later stage is cancelled or retargeted. Track source-space versus document-working colours so reused data receives the correct colour conversion once.
- Refresh an owned mesh clone when the visible source mapping is unchanged. Write points, polygons, colours, opacity and weights in bounded native batches. UVW coordinates use Cinema 4D's supported `SetSlow` API; raw UV buffer layout is not assumed.
- Compensate opacity for the area added by Pixel Footprint filtering. Fine bright splats no longer keep their original peak opacity after being enlarged by the filter. Source RGB, SH coefficients and stored opacity remain unchanged; the correction applies only to supported camera-facing projection with a nonzero filter.
- Bundle the unchanged, checksum-pinned NumPy 2.2.6 wheel for Windows x64 / CPython 3.11. Extract it to the plugin's private local cache without pip, downloads or changes to Cinema 4D's Python installation. Reuse an available NumPy and fall back to ordinary Python when acceleration is unavailable.
- Restrict release packaging to that exact wheel and preserve its complete upstream license notices.
- Evaluate all four candidate directions for enclosed scans, even when the first direction is unsuitable. Measure coverage with the filter-compensated opacity and the actual visibility cutoff.
- Preserve manual film offsets and parallel zoom on an automatically created import camera when the source changes.
- Report authored 2D Gaussian PLY models as unsupported 2DGS rather than a misleading missing `scale_2` error; preserve normal 3DGS validation.
- Keep small camera movements significant in cache keys when the scene is far from the world origin, while filtering insignificant matrix noise.
- Include object and parent scale/shear when choosing the near clipping distance of an inferred interior view; avoid subtracting large translated positions to compute its direction.

### Compatibility

Pixel Footprint now changes peak opacity as well as projected size. Existing scenes using a nonzero filter can therefore render fine bright detail differently after updating. Set Pixel Footprint to 0 to disable both filtering and its compensation. Normal Redshift materials, lighting and linear-light compositing remain in use; this is not a replacement Gaussian compositor or a global gamma adjustment. See [rendering compatibility](docs/rendering-compatibility.md).

## 0.8.2 — Import scheduling, viewport responsiveness and source validation

- Build native points incrementally instead of retaining millions of temporary Vector objects and committing them in one call. Card batches target 4 ms, up to 256 cards; native allocation and cloning remain indivisible.
- Select visible cards in the cancellable worker. Reuse unchanged point-preview buffers and prepared data held by other live scan objects.
- Yield briefly at worker checkpoints so CPU-heavy preparation continues to deliver host timers, UI progress and cancellation without changing Python's process-wide scheduler.
- Resolve actual SH degree without replacing the job request captured by the mesh builder. This avoids a second full import when the first material is created and unnecessary SH0 view updates.
- Keep Cancel effective across camera movement; explicit Reload or a source/control change can resume processing. Do not hide worker failures behind camera retargeting.
- Keep automatic framing diagnostics local to each scene when source analysis is reused.
- Recheck available RAM against actual visible card allocations after CPU preparation and before attribute-refresh mesh cloning; preserve the previous complete model on refusal.
- Correct parallel-camera SH direction and cache invalidation.
- Respect Film Offset and RS Sensor Shift when culling projected cards; use evaluated native Redshift camera intrinsics for perspective and parallel projection.
- Match SuperSplat's normalized Gaussian opacity tails and center opacity, with a unique OSL kernel and safe migration of unchanged built-in shaders. Preserve hand-edited shaders.
- Trim card boundaries to the corrected opacity cutoff while preserving the UV mapping and visible Gaussian footprint; avoid tracing shader-zero borders.
- Harden release packaging against caches, private configuration, dependencies and model weights.

### Compatibility

The Gaussian profile changes the appearance of saved scenes using the unchanged built-in shader. Redshift still uses editable polygon cards: dense/coplanar intersections, finite transparency depth, color compositing and camera publishing effects can differ from a dedicated Gaussian renderer. This release does not promise identical output in every scene. See [rendering compatibility](docs/rendering-compatibility.md).

## 0.8.2-dev — Automatic SOG views

- Use full source retention by default, without the optional import-quality prompt; preserve saved/manual limits and memory checks.
- Keep the first camera near the dense capture region when distant environment splats form a long spatial tail. This changes framing only.
- Evaluate fine projected coverage at the SOG origin to select a capture-space view for suitable enclosed scans, then compare four horizontal directions to avoid close blurred surfaces; retain the subject overview otherwise.
- Preserve existing scene cameras and explicit AI camera metadata.
- Use the neutral OCIO view for a first SOG import into an empty scene with the default ACES view; preserve existing scenes, custom views, and subsequent manual colour choices.
- Trim only shader-zero Gaussian tails and remap UVs with their support, reducing wasted Redshift transparency intersections without deleting visible source detail. Opacity edits update support as well.
- Avoid decoding already validated compact native PLY records twice; retain full-source validation and effective SH detection.
- Release large transient buffers when native objects are destroyed, including wrappers retained by undo/render events.

### Validation and known limitations

- Development prerelease: 249 automated tests pass. Native Cinema 4D/Redshift testing has reached eight of fifteen SOG fixtures; final-profile regression and the remaining fixtures are not complete.
- Closely spaced or coplanar transparent Gaussian cards can lose layers in Redshift, producing bright patches in dense scenes. This remains unresolved; the rendering backend is still Gaussian cards, not a dedicated Gaussian rasterizer.
- Experimental depth offsets, alternative colour-compositing profiles and increased transparency depth are not included in this release.

## 0.8.1 — Clearer Help and documentation

- Expand Help's reading area and add an optional resizable reader window.
- Add Boosty support and the installed plugin version below Help.
- Simplify English/Russian documentation and remove machine-specific validation reports.

## 0.8.0 — Import quality and bilingual Help

- Add LOW, MEDIUM, HIGH, MAX and custom import budgets, with a choice window for large files.
- Preserve full opacity-eligible source data in MAX when memory permits; compact SPLAT/SPZ storage.
- Add offline English/Russian Help, separate media INPUT from SCAN, and group manual tools.
- Set new-object point preview to 50,000; preserve saved values.

## 0.7.2 — SOG orientation

- Automatically convert conventional SOG orientation for new objects; preserve existing scenes.

## 0.7.1 — Large scans

- Improve source decoding and discard obsolete camera calculations without rereading scans.

## 0.7.0 — First view

- Add automatic framing, manual overview cameras and source summaries.

## 0.6.2 — Projection

- Correct near-camera projection and add automatic Redshift preparation.

## 0.6.1 — Defaults

- Use source-fidelity appearance settings for new objects while preserving existing scenes.

## 0.6.0 — Interactive updates

- Reuse prepared source/geometry/colour data and reduce interruptions during camera or LOOK edits.
- Add perspective pixel filtering and compact preparation buffers.

## 0.5.1 — Licenses

- Complete third-party notices and clarify distribution terms.

## 0.5.0 — Installation

- Automatically install private Python, dependencies and converters; reuse existing working runtimes.

## 0.4.0 — Input and progress

- Add background scan loading, batched geometry assembly and cancellable updates.

## 0.3.2 — Support links

- Link directly to one-time Boosty donations and simplify bundled instructions.

## 0.3.1 — Support

- Add optional author support from inside the plugin.

## 0.3.0 — Initial public release

- Publish image-to-3D generation, scan import, Redshift materials and MoGraph tools.
- Add video/sequence frame selection, progress/cancellation and finer control steps.

## 0.2.0 — Appearance

- Reuse geometry for LOOK edits; add source-fidelity and camera tools.

## 0.1.1 — Rendering

- Keep render geometry available when point preview is enabled.

## 0.1.0 — Local development

- Initial Gaussian object, importers and local AI integration.
