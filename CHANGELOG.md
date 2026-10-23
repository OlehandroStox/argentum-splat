# Changelog

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
