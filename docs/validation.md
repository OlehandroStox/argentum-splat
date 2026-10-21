# Validation scope

Version 0.3.0 was tested on **Windows, Cinema 4D 2027.0.0 and NVIDIA RTX 4070 12 GB**. These results describe that setup; they are not a compatibility guarantee for other versions or hardware.

## 0.3.1 support button

The 95 portable tests pass again. In the running C4D 2027.0.0 instance, the button description was verified below Status. Its command dispatch was checked with browser success, failure and exception responses: the exact Boosty URL was requested, and object data and Status stayed unchanged. These checks used refreshed Python callbacks; a cold application restart and a real donation were not tested for this patch. Generation and rendering code were not changed.

## Portable tests

95 tests were run with Pillow and PyAV installed, without skipped media tests. They cover:

- PLY/SPLAT/SPZ parsing, malformed input and finite numeric values.
- Gaussian geometry, coordinate transforms, colour correction and SH.
- Source-camera decoding and missing/invalid metadata.
- Source/asset paths and extra-format converter selection.
- Image, video and sequence routing; exact decoded frames, missing/out-of-range frames and alpha.
- Incremental progress records, including partial UTF-8/JSON writes.

Run the included suite with `python -m unittest discover -s tests -v` after installing `requirements-test.txt`. This does not require C4D or model weights and does not test native rendering.

## Native checks performed separately

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
