# Validation scope

Version 0.3.0 was tested on **Windows, Cinema 4D 2027.0.0 and NVIDIA RTX 4070 12 GB**. These results describe that setup; they are not a compatibility guarantee for other versions or hardware.

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
