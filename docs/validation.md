# Validation scope

## 0.7.2 five real SOG imports with untouched model defaults

**227 portable tests pass on Python 3.10 and 3.12.** Native validation used a cold restart of Cinema 4D 2027.0.0, Python 3.11.4, RTX 4070 12 GB and 32 GB system RAM. Each SOG was selected on a fresh object in a separate empty document. Output was 1280 × 720; LOOK, import cap, opacity, scale and generated cameras were not manually tuned. All five Redshift renders completed with result 0 and their actual OCIO display images were inspected.

| Source | Retained / source splats | Preparation reported by plugin | Render |
|---|---:|---:|---:|
| porsche | 624,332 / 625,597 | 73.6 s | 42.6 s |
| The Fruit Bowl | 748,470 / 750,322 | 87.5 s | 15.8 s |
| Fungus (Chicken of the woods) | 657,340 / 660,490 | 76.4 s | 23.0 s |
| Cobweb Scope — synthetic Gaussian splat | 4,000,000 / 5,890,142 | 493.0 s | 56.1 s |
| Parish Church of Saint Maurice | 4,000,000 / 9,975,598 | 516.0 s | 20.2 s |

The previous defaults displayed Porsche upside down and the underside of the fruit bowl and ground/fungus scan. The SOG coordinate correction produced recognizable, upright first views for these three models. Cobweb Scope and its fine threads were recognizable, but the 4-million cap retained only 67.9% of its source records. **The church failed the strict default-view visual test**: an exterior overview of the interior scan showed diffuse patches, and only 40.1% of its source records were retained. No manual camera correction was substituted for that failure. This release therefore **does not guarantee a useful first view for every scan**, especially interiors, and it does not preserve all detail above the import cap. Pixel-identical comparison with a native Gaussian rasterizer was not performed.

The large files required about 8–9 minutes of preparation; these measurements must not be described as instant loading. The progress window remained present; the longest measured UI assembly slice for Cobweb was 1.20 s. Unchanged reloads of the fruit bowl, fungus, Cobweb and church reused the exact parsed cloud, spatial arrays, colours and mesh template without starting a job.

Native save/reopen checks confirmed that pre-0.7.2 scenes retain Auto SOG Orientation off, while new scenes preserve the enabled setting. Existing Image/PLY and SPZ coordinate paths are unchanged. Full MoGraph animation and AI inference were not rerun in this patch.

Sources were private local test inputs; scans, saved test scenes and derivative renders are **not distributed in this release**. Source credits: [porsche by VODKIN](https://superspl.at/scene/815d7ba0), [The Fruit Bowl by SuperDelphi](https://superspl.at/scene/d8ba72a6), [Fungus by Natural Ai App](https://superspl.at/scene/9ba34048), [Cobweb Scope by Dan Barash](https://superspl.at/scene/73614e89), and [Parish Church of Saint Maurice by Pavel Tanhäuser](https://superspl.at/scene/15a202e6). The church's bundled notice specifies CC BY-NC-ND 4.0; the other four specify CC BY 4.0.

## 0.7.1 large environments and obsolete camera work

**222 portable tests pass on Python 3.10 and 3.12.** Added checks cover selective attribute decoding for all supported SH degrees, big/little endian and mixed float/double layouts; compact card selection and source order; hierarchy-driven invalidation; environment tails at multiple scales; camera settling, cancellation and restart without discarding the parsed source.

Native **Cinema 4D 2027.0.0 / Python 3.11.4 / RTX 4070 12 GB / 32 GB system RAM** validation used the user's `Where it belongs.sog` (3,999,516 source records). The old 3-million cap sampled 982,148 otherwise eligible records. With the new 4-million cap, all **3,982,148 opacity-eligible splats** were retained (**99.57%** of source); **17,368** were below 1/255. There was no reservoir sampling. At the preserved user camera, **895,177 nonzero projected cards** were emitted, while all retained source records and preview data stayed available.

Full parsing/preparation/assembly took **339.15 s**: **77.66 s** reading, **142.20 s** geometry and **86.19 s** SH3 colour; the longest measured assembly slice was **0.928 s**. Its **1280 × 720 Redshift render** completed with **result 0 in 82.89 s**. The native ACEScg → ACES 2.0 SDR-video / sRGB display image was inspected: bicycle frame, wheels/spokes and tree-bark detail were recognizable, without the obsolete-view large-card breakup. Fine translucency/texture and colour differences from a dedicated rasterizer remain. The scan and render are not included in the release.

A 3-million retained update with the optimized path took **197.02 s** (107.88 geometry, 64.63 colour) and emitted 674,890 cards. Earlier updates took 413.95–461.53 s. Camera framing changed during the session, so these observations are **not a controlled speedup ratio**. The old baseline final render was already recognizable after waiting for preparation; this patch must not be described as fixing a parser that had rejected the file.

An isolated **80,000-splat native test** changed the camera during preparation: one obsolete pass stopped, the latest camera key became ready, and read time remained effectively zero because the cloud was reused. Native tag checks verified that compact cards and subsequent colour/opacity edits map to the correct source records. A parent disabled compaction and preserved per-source indexing. An unchanged reload of the full user scan reused the exact cloud, spatial arrays, colours and mesh template. The user's camera was unchanged; the final editable scene was saved separately. The full MoGraph animation suite was not rerendered in this patch.

The real source's old framing bounds were dominated by a distant environment shell. The new bounded analysis selected a central region for framing only, and native camera creation from that report was checked in an isolated document. This is an overview heuristic, not a reconstruction of the website's authored camera or a guarantee of correct subject framing/orientation. No source points are removed by it.

The modules/callbacks were refreshed in the running application; a cold restart was not repeated. IPR can still display previous-view cards while a real camera change is preparing. Wait for Ready at the intended camera before judging final import quality. Large sources still take minutes; the cap is finite, and Redshift cards do not promise pixel-identical native Gaussian compositing.

Private diagnostic source: [Where it belongs by Muhammad Ichsan](https://superspl.at/scene/6ca913aa), whose bundled notice specifies CC BY-NC-SA 4.0. No source scan or derivative image is distributed here.

## 0.7.0 automatic import framing

**214 portable tests pass on Python 3.10 and 3.12.** Added checks cover scales from 1e-6 to 1e6, portrait/square/wide aspect ratios, off-origin geometry, floaters, thin/flat bounds, camera ownership and user overrides, source-matched AI metadata, changed-limit summary refresh, cancellation of bounded analysis, and reuse of a parsed cloud between analysis and final-view preparation.

Native Cinema 4D **2027.0.0 / Python 3.11.4 / RTX 4070 12 GB** checks used isolated documents. A 2,048-splat coloured sphere at source scales **0.001 and 1,000** (a millionfold size difference) automatically received a fitted camera. Both **320 × 320 Redshift renders** finished with result 0, in **1.843 s and 1.765 s** respectively. Both visible bounds were **(80, 80)–(240, 240)** pixels; mean absolute RGB differences were **0.137 / 0.124 / 0.116** on a 0–255 scale. Both display images were inspected. This checks scale-relative framing/clipping, not million-splat loading speed.

A generated 2,048-splat **SOG** passed through the installed converter and received the fitted camera automatically. An existing **65,536-splat image-generated house PLY** used its matching `generation.json` source view; loading/preparation took **9.71 s** and its **320 × 320** Redshift render finished with result 0 in **4.031 s**. The inspected display image showed the house fully framed. AI inference was not rerun in this patch. Import analysis examines at most 8,192 records; source data is reused for the second preparation stage.

Native checks also confirmed: an existing camera stayed unchanged; the Frame Loaded Scan button created a separate camera; changing source reused an untouched import camera; editing that camera prevented automatic replacement; manual clipping edits were respected; an unchanged Reload reused source, spatial, colour, mesh and analysis objects; save/reopen retained the ownership link and source marker. New controls were verified in the native description, including a non-editable Source Summary. The original user document remained active with unchanged root identities/transforms, and all isolated test documents were closed afterward.

Callbacks/modules were refreshed in the running application; a cold restart was not repeated. The previous 0.6.2 full-source Iowa render below remains the large-scan rendering check; that expensive render was not repeated because 0.7.0 does not change projection math or shaders. Camera-facing updates still require preparation for a genuinely new view. A fitted overview cannot recover arbitrary source orientation, physical units or a website's camera/post effects. Existing scenes keep their saved settings and the default import cap remains 3 million splats.

## 0.6.2 large-scene projection

**199 portable tests pass on Python 3.10 and 3.12.** New checks cover eye-plane singularities, behind-camera collapse, bounded projected support, image-edge overlap, source-index preservation, camera invalidation with Pixel Footprint 0, and once-per-source Redshift preparation. Render-setting floors and the saved source marker share one undo operation; stricter values remain intact.

Native Cinema 4D **2027.0.0 / Python 3.11.4 / RTX 4070 12 GB** loaded all **2,999,952** records of the Iowa Capital Building SOG, with no reservoir sampling or opacity rejection. Its previous image had long horizon streaks and a coarse, blob-like facade. On a deterministic 20,134-record sample at the user's camera, the old projection produced a card half-axis of approximately **278,192 cm** near the camera plane. The bounded projection removes this singular behavior and collapses behind-camera cards instead of substituting tilted geometry.

At the same user camera, the corrected full-source **1091 × 1280** Redshift float render finished with **result 0 in 82.95 seconds**. Its native **ACEScg → ACES 2.0 SDR-video / sRGB** display image was inspected: facade/roof/vegetation details were substantially clearer, and the long horizon streaks were absent. Transparency depth was raised from **16 to 128**, with manual **16/128** samples and adaptive threshold **0.01**. This checks the combined correction; it is not a pixel-identical comparison against the website, which uses a different camera and display transform. Distant source detail and card-compositing differences remain.

With the already-parsed source reused, geometry preparation took **156.97 s**, SH3 colour **92.87 s**, and the full update including C4D assembly **400.51 s**. The longest recorded assembly slice was **0.991 s**. These are single-run measurements, not a real-time navigation claim or a controlled speedup ratio. Camera-facing updates on a 3-million-splat scene still take substantial time.

Twelve equivalent native matrix round-trips and an unchanged explicit reload retained the exact source, spatial, colour and mesh-template objects without starting a new job. A later manual transparency-depth edit was preserved by the automatic preparation hook. An isolated save/reopen test preserved both the source marker and the user's disabled auto-prepare checkbox. Updated callbacks were refreshed in the running application; a cold restart was not repeated for this patch. No new MoGraph animation benchmark was run. Camera-facing culling is specific to the projection camera; use surface-aligned cards for secondary views or movement across frame boundaries.

Test source: [Iowa Capital Building by weitzvdc](https://superspl.at/scene/131f8717), listed under CC BY 4.0. The scan is not bundled with the plugin.

## 0.6.1 default fidelity

**192 portable tests pass on Python 3.10 and 3.12.** The new import regression retains all 262,145 records of a binary PLY with alpha 0.01: more than the previous import cap, and below the previous opacity threshold. Other new checks cover clone preservation, the explicit preset retaining artistic values and a lower opacity threshold, and new-material fallback weights without overriding explicit older weights.

Native Cinema 4D **2027.0.0 / Python 3.11.4** checks confirmed all new-object parameters and Attribute Manager default metadata. Cloning preserved custom parameters and camera/material links. A saved custom-value fixture was reopened and retained its values and remapped links. A new-object fixture loaded 25 Gaussian cards and completed a **320 × 320 Redshift render** with result 0 in **0.781 s**; its OCIO display-transformed output was inspected and contained the coloured Gaussian pattern. This small render checks integration, not large-scan performance or visual parity with another renderer.

The user's already-loaded Strawberry (1,499,098 splats) and Raspberry (2,309,943 splats) retained their parameters and the exact same source, spatial, colour and mesh-template objects through the update. No scan job was queued and the active document stayed unchanged. The updated modules were refreshed in the running application; a full restart was not repeated for this patch. The source-fidelity settings had already been exercised on the larger scans in 0.6.0. Higher default retention does not make large imports or real camera-facing view changes instantaneous.

## 0.6.0 cache and scan detail

**187 portable tests pass on Python 3.10 and 3.12.** New cases cover quiet camera updates, coalescing while a camera job is running, canonical inactive-SH keys, render clones with evicted global cache entries, compact binary PLY sampling/storage, float64 geometry buffers, perspective covariance projection under nonuniform object transforms, camera-matrix round-off, informational camera-override warnings, and manual quality settings that preserve stricter values. Finite-difference projection tests also cover lens, camera and output-resolution changes.

Single-run CPU colour comparisons, 262,144 splats, Python 3.10, without NumPy:

| Colour pass | Before | 0.6.0 |
| --- | ---: | ---: |
| SH0, neutral correction | 2.102 s | 0.723 s |
| SH3 | 5.742 s | 3.432 s |

Maximum RGB error against the scalar reference was 1.89e-15. These measurements exclude C4D attribute writes and Redshift convergence. Run `python tests/test_color_performance.py --benchmark` to reproduce the fixture.

A separate-process 20,000-record SH3 PLY test retaining 4,000 records reduced the tracked sampling-stage peak from 11.81 MB to 3.85 MB and the overall peak from 11.81 MB to 10.11 MB. Time with tracemalloc enabled was 0.707 s before and 0.573 s after. The final selected-cloud hash matched exactly. These small-fixture measurements are not peak process memory estimates for a million-splat C4D scene.

In Cinema 4D 2027.0.0, automatic SH-camera updates kept the processing dialog closed and reused the loaded cloud and spatial arrays. Camera motion during a job did not cancel it; the settled result matched the latest camera key. Light-only edits did not queue preparation. A matching render clone reused cloud, spatial and colour arrays. The main 0.6.0 changes also loaded after a cold application start; subsequent round-off, camera-warning and quality-preset fixes were checked with refreshed callbacks.

For 50,000 retained SH3 records in separate processes with tracemalloc, compact cloud storage used 14.45 MB instead of 121.26 MB (88% less); peak after geometry and colour preparation was 50.63 MB instead of 157.41 MB. Repeated transient decoding adds CPU cost to subsequent passes. A separate 50,000-splat projected-geometry/colour fixture reduced prepared-array storage from 34.54 MiB to 5.96 MiB (82.8%), taking 2.037 s instead of 1.992 s. These are component measurements, not total C4D RAM guarantees. The outputs match the list-based calculations.

The native large-scan check loaded 2,309,943 eligible splats from a 2,370,630-record SOG with the 3,000,000 cap: all opacity-eligible records, without reservoir sampling. The already-converted PLY took 45.51 s to read/decode, 137.68 s for perspective geometry, 69.66 s for SH3 colour, and 367.67 s overall including C4D assembly. The longest recorded assembly slice was 0.681 s. Before compact cloud/buffers, a smaller 1,000,000 retained sample in the same long-running application took 676.40 s overall (353.43 s reading/decoding). This is a single comparison with different retained counts and memory pressure, not a controlled universal speedup ratio. Large source-fidelity scenes still need substantial preparation time.

A 1,000,000-splat Redshift preview completed. The first full 2,309,943-splat render did not complete: Cinema 4D closed with Windows exception 0xC00000FD at an address inside nvcuda64.dll while another view was being prepared. This records a host stack-growth failure, not a proven GPU-memory or driver root cause. The test inherited a maximum of 8,192 samples and enabled GI. After restoring the saved scene and running sequentially, a full-source 768 × 460 Redshift render completed in 235.25 s with result 0 and a written file. Cloud, geometry, colour arrays and mesh template were reused, with no preparation job queued. Later fixed-snapshot float renders also completed. These successful runs do not establish the cause of the earlier crash or universal host stability.

The new perspective pixel filter remains an approximation on flat cards. The source-fidelity preset retains at most 3,000,000 splats; larger scans remain sampled. No pixel-identical match with a dedicated Gaussian viewer is claimed. Native colour management, ray ordering and the renderer's alpha kernel also affect the result.

A subsequent full-source **1536 × 920** Redshift float render completed in **48.58 s** with manual 16/128 samples, transparency depth 128 and Pixel Footprint 0.075. The display image was exported through the snapshot's native OCIO rendering-to-display transform. The camera/framing and resolution differ from the earlier 235.25-second run, so these timings are not a speedup comparison. Twelve native camera matrix round-trips/evaluations reused source, spatial arrays, colours and mesh template without queueing preparation. A real view change on this 2.31-million-splat scene still required about 325 s including geometry, SH and native assembly; quiet updates do not mean instantaneous full-source camera-facing preparation.

The fidelity check found an explicit projection-camera override differing from the render camera, and an oversized pixel footprint caused by confusing actual-pixel and doubled-projection coordinates. The preset now uses 0.075 actual pixel squared. Fine features are improved, but differences in translucent colour and layer compositing remain visible. SOG data does not include the website's complete camera/post-effect/render configuration.

An isolated OSL diagnostic using the same shader entry name for a different program invalidated Redshift's emission kernel. A distinct versioned entry name restored rendering; the release migrates only the exact unmodified legacy emission source. Custom shader text is preserved. Subsequent native rendering used the release shader. This diagnostic is not evidence that every black render has the same cause.

## 0.5.1 license update

112 portable tests passed. The two edited setup scripts parse successfully. License texts were checked against pinned upstream sources; release contents were inspected for runtime/model binaries. No geometry/rendering behavior changed; native rendering was not rerun for this documentation/notice update.

Version 0.3.0 was tested on **Windows, Cinema 4D 2027.0.0 and NVIDIA RTX 4070 12 GB**. These results describe that setup; they are not a compatibility guarantee for other versions or hardware.

## 0.5.0 installation and native regression checks

**112 portable tests pass**, including malformed/truncated runtime checkpoints and recovery from corrupt resumable PyTorch chunks. Windows PowerShell 5.1 installation checks cover:

- Downloading private CPython 3.12.15 into an empty runtime directory, creating venv/pip without using system Python, and reusing it without rewriting the environment. First bootstrap took 19.0 seconds on the test connection; this excludes AI packages/models.
- Recovery from a corrupt Python archive, incomplete extraction and broken venv, preserving the old files in backups. Paths containing spaces and Cyrillic characters also work. User and machine PATH remain unchanged.
- Full installer orchestration with an existing ready AI environment; plugin backup, partial dependency failure, import-only mode, unique run reports and dependency setup launched from the already-installed plugin folder.
- Fresh portable Node/converter installation and actual conversion of a SOG fixture. A deliberately failed converter repair preserved the previous manifest and working converter.

A fresh CPython 3.12.15 environment installed the CUDA packages and verified all five model hashes successfully in 450 seconds; a repeated setup completed in 3.9 seconds without downloads. The checkpoints were reused through local hard links and fully hashed, rather than downloaded again. This tests a clean Python runtime on the existing machine, not a separate clean Windows installation.

That new environment generated 65,536 Gaussians from the bundled house reference at 20 steps / seed 42 in 42.7 seconds. Both resulting PLY and SPLAT files passed the plugin's full reader validation with 65,536 finite records and matching positions (allowing for their different ordering). The 112-test portable suite also passes under this Python 3.12 environment.

The in-plugin setup action was also run in a temporary native C4D document using the refreshed 0.5.0 callbacks: setup exited successfully, its run ID matched the report, ready dependencies were reused, Status updated and the progress window closed. The user's original scene, Status and loaded geometry remained unchanged.

In C4D 2027.0.0, a 1,024-splat fixture retained its geometry hash through 12 camera/light changes and six render/editor/export evaluation contexts. An animated MoGraph Plain Effector moved every card through 0–25 cm across 13 evaluated frames. An animated Bend deformer also preserved all cards; its render clone matched the evaluated geometry. UVs and per-card attributes were retained.

For SH3, camera movement reused spatial data and changed only colours after settling. Camera-Facing Cards intentionally updated orientation while retaining the previous complete model during processing. Two actual Redshift previews completed with nonempty output and unchanged source geometry. These are functional checks on a small fixture, not FPS measurements for large MoGraph scenes.

Live RS Render View start/stop could not be confirmed through the available command-state API without operating its window; no success is claimed for that additional test. Renderer sample accumulation can restart when the camera or lights change even though the splat geometry remains intact. No cold application restart was performed for this update.

The Windows integration scripts are `tests/test_installer_python.ps1` (real Python download) and `tests/test_install_workflow.ps1` (isolated installer/failure fixtures). Pass a new dedicated `-RuntimeDir` or `-TestRoot`, respectively. They preserve their outputs for inspection.

## 0.4.0 scan pipeline

**105 portable tests pass**, including all media tests with Pillow/PyAV installed. Added checks cover deterministic sampling, invalid records outside the retained sample, cancellation while reading/smoothing, atomic worker results and camera dependencies. A separate comparison against 0.3.2 preserved sampled SPLAT attributes/bounds exactly and produced identical smoothed normals for 4,000 randomized inputs.

Single-run CPU comparisons in an external Python 3.14.6 process, retaining 262,144 splats in both versions:

| Stage / input | 0.3.2 | 0.4.0 |
| --- | ---: | ---: |
| Read binary Gaussian PLY, 2,999,952 records, SH3 | 70.55 s | 28.75 s |
| Prepare geometry, same PLY sample, smoothing 2 | 12.54 s | 7.45 s |
| Read SPLAT, 1,048,576 records, SH0 test fixture | 10.38 s | 5.26 s |

These stage measurements exclude conversion, C4D assembly and rendering. They are not viewport-FPS measurements or universal speedup claims. SOG conversion also no longer triggers a separate full validation read before the scan reader.

In **Cinema 4D 2027.0.0 / embedded Python 3.11.4**, the large SOG's already-converted PLY loaded from an empty parsed-data cache in **75.55 s** overall, including background preparation and native mesh assembly. Starting the job returned in **0.014 s**. During parsing, an editor evaluation completed in **0.113 s**; the longest recorded assembly batch was **0.096 s**. The existing complete model remained available during processing. First-time SOG conversion adds its own time.

Twelve camera-change evaluations on the loaded large scan took **0.0054 s total**, before the deferred SH update. The subsequent SH-colour update took **8.59 s**, reused the spatial arrays, and did not re-read the file or smooth normals. Camera-Facing Cards was off. Actual viewport drawing/FPS and Redshift convergence were not benchmarked.

Native checks also covered fresh SPLAT loading; fresh SOG conversion through the installed converter; progress-window creation/closure; cancellation during reading and between staged attribute writes; retention of the previous model after cancellation or malformed input; unchanged reload; weight/colour edits without geometry changes; scene save/reopen; offline render evaluation; Make Editable; and closing a document during a scan job. A small Redshift preview confirmed material/colour output after the asynchronous import. Geometry was compared structurally; no new photorealistic-quality claim is made.

Source Fidelity also returned immediately into a scan job (0.017 s for the test fixture); its reload and camera-facing geometry completed with a material and closed the progress window. The callbacks were refreshed in the running application and saved scenes were reopened. A complete application restart was not repeated for this update. Native resource allocation, renderer evaluation and GPU memory limits still impose costs; the worker does not make a multi-million-record first load instant.

## 0.3.1 support button

The 95 portable tests pass again. In the running C4D 2027.0.0 instance, the button description was verified below Status. Its command dispatch was checked with browser success, failure and exception responses: the exact Boosty URL was requested, and object data and Status stayed unchanged. These checks used refreshed Python callbacks; a cold application restart and a real donation were not tested for this patch. Generation and rendering code were not changed.

## 0.3.x portable tests

The 0.3.x suite contained 95 tests, run with Pillow and PyAV installed without skipped media tests. They cover:

- PLY/SPLAT/SPZ parsing, malformed input and finite numeric values.
- Gaussian geometry, coordinate transforms, colour correction and SH.
- Source-camera decoding and missing/invalid metadata.
- Source/asset paths and extra-format converter selection.
- Image, video and sequence routing; exact decoded frames, missing/out-of-range frames and alpha.
- Incremental progress records, including partial UTF-8/JSON writes.

Run the included suite with `python -m unittest discover -s tests -v` after installing `requirements-test.txt`. This does not require C4D or model weights and does not test native rendering.

## 0.3.x native checks performed separately

- Restarted C4D and checked visible object registration, hidden duplicate command, toolbar command and 0.1 parameter steps.
- Opened the selected video frame in Picture Viewer.
- Generated 65,536 Gaussians from video frame 1, 20 steps, seed 42; loaded the result and its material in C4D. AI processing was 43.11 seconds in this run.
- Checked progress-window position, status updates, successful completion and worker cancellation, including closing the window.
- Earlier native checks covered Redshift IPR/final rendering, per-object material weights, colour management, MoGraph and assets.

Private scene files, local machine paths and raw native validation logs are not part of the public package. The portable suite is the reproducible part of this repository; native checks require a licensed C4D/Redshift installation.

## LOOK optimization measurement

One controlled local comparison used the same 260,533 loaded splats and Minimum Opacity 0.001. CPU update time was measured through C4D `ExecutePasses`:

| Change | Before 0.2.0 | After 0.2.0 |
| --- | ---: | ---: |
| Emission weight | 1,525 ms | 31 ms |
| Gamma | 21,199 ms | 3,045 ms |

These were single measurements, not a statistical benchmark. They exclude Redshift convergence and final render time. Geometry hashes were unchanged; a fixed-settings render comparison after the optimization was pixel-identical. This is evidence of reduced update work, not a promise of instant rendering.

## Not validated or not implemented

macOS, AMD inference, older C4D releases, multi-GPU operation, render farms, multi-view training, 4D generation, hair grooming and physical eye reconstruction are not claimed. Development plugin IDs can conflict with other plugins. Redshift cards approximate Gaussian rendering and do not replace a dedicated rasterizer.
