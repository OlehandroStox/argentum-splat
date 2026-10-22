# Controls

[Back to README](../README.md) · [Русский](controls.ru.md)

Labels match the plugin's English interface. Decimal LOOK controls increment by **0.1**; type a value for finer precision. Minimum Opacity increments by **0.001**. Existing values and animation keys are not rounded.

## New-object defaults (0.6.1)

New objects start with **Source Fidelity**: Maximum Splats **3,000,000**, Minimum Opacity **1/255 ≈ 0.00392157**, Camera-Facing Cards **on**, Pixel Footprint **0.075**, SH degree **3**, SH Strength **1**, Normal Smoothing **0**. LOOK starts with **sRGB Source to Scene Linear**, Highlight Limit **3**, Emission **1**, Diffuse **0**, Subsurface **0**. Global Scale **100**, Splat Scale **1** and Opacity Multiplier **1** remain unchanged.

The previous 262,144 import cap could discard most of a detailed scan; the 0.02 opacity threshold could remove faint details. Diffuse 1 added scene lighting to captured colours. The new defaults retain more source information without requiring the preset after every import. Attribute Manager's Reset to Default uses the same values.

**Existing and duplicated objects keep their saved values.** Apply Source Fidelity explicitly to an older object. It preserves colour correction, scale, axis conversion and a lower opacity threshold. The preset does not reset a deliberately chosen Colour Management mode.

Large imports and camera-facing updates need more time and RAM than a reduced scan. Point Preview stays on at **10,000 points**; it only reduces editor drawing. For draft work, lower Maximum Splats or turn Camera-Facing Cards off, accepting reduced detail or projection accuracy. Restore Source Fidelity for final work. Gaussian Count controls AI generation separately; the 3-million import limit does not create extra Gaussians.

## Input

| Control | Meaning / when to use it |
| --- | --- |
| Input File | Image, existing splat, video or a selected numbered image. File extension selects the pipeline in Auto mode. |
| Input Mode | Auto for normal files; Numbered Image Sequence to interpret the frame field as an offset from the selected filename. |
| Source Frame / Sequence Offset | Zero-based decoded frame for video/animated images; numeric filename offset for sequences. `clip.mp4`, 0 = first frame. `shot_0100.png`, 2 = `shot_0102.png`. |
| Preview Selected Frame | Extract the selected frame and open it in C4D Picture Viewer before generation. |
| Gaussian Count | Target generation count: 65,536 / 131,072 / 262,144. Affects new AI results only; 262,144 is the upstream model's maximum. |
| Generation Steps | AI sampling steps, 1–100. Default 20. More steps take longer and may not improve every input. |
| Seed | Random seed for the prediction. Keep fixed for comparisons; change to explore a different result. |
| Alpha Erosion | 0–8. Shrinks the alpha mask after background removal. Keep 0 for delicate edges; use a small value to remove a fringe. Applies only to the next generation. |
| Output Folder | Where generated files are saved. Default: `%LOCALAPPDATA%\ArgentumSplat\generated`. Each job has its own directory. |
| Load / Generate from Input | Generate from an image/frame, or directly load/convert an existing splat file. |
| Cancel Processing | Stop the background worker and its child processes. The progress window's Cancel and close button also cancel. |
| Set Up AI / Extra Formats | Install the isolated Python AI environment and the optional format converter. Requires internet during setup. |
| Open Output Folder | Open the output location in Explorer. |

Generation, conversion, initial scan loads, changed source/loading settings and explicit **Initialise / Reload** show a progress window with Cancel. It covers **SCAN reading, geometry preparation and C4D assembly**, showing the stage, available progress and elapsed time. Setup/conversion stages without a measurable total show activity. Ordinary camera and LOOK updates report progress in **Status** without opening this window; use **Cancel Processing** to stop them.

Scan reading/calculation runs in a worker; C4D geometry is assembled in short UI-thread batches. Cancellation keeps the previous complete model. A single native allocation/commit must finish before cancellation can take effect.

## Scan and detail

| Control | Meaning / when to use it |
| --- | --- |
| Splat File | Direct source path for an existing scan. Loading is queued after changes settle; Initialise / Reload starts it immediately or retries a cancelled/failed request. The unified Input File is an alternative. |
| View-Dependent Colour | Evaluate up to SH1, SH2 or SH3 if the file contains those coefficients. Off keeps the base colour. TripoSplat outputs SH0, so its SH controls are unavailable. |
| Camera-Facing Cards | Project the Gaussian covariance into the selected camera plane. Off uses the two largest Gaussian axes for each card. Camera-facing mode needs extra work as the camera moves. |
| Projection Camera | Explicit camera for SH and camera-facing cards. Empty uses the render camera, falling back to the editor camera. Status warns when the override differs from the render camera; clear the link to follow camera switches. |
| SPZ: Unconverted Coordinates | Keep SPZ's source RUB coordinates. Normally position, rotation and SH are converted together. Flip Y is applied afterward. |
| Normal Smoothing Passes | 0 disables; 1–8 averages nearby normals with aligned orientation. Does not blur the positions. |
| Initialise / Reload | Load or refresh the scan with progress and Cancel. Unchanged source/settings reuse prepared data; file timestamp/size and loading settings invalidate the relevant caches. It does not rerun AI. |
| Source Fidelity – Preserve Detail | Set Maximum Splats to 3,000,000, SH3 / SH Strength 1, Emission 1, Diffuse 0, Subsurface 0 and Normal Smoothing Passes 0. Enable Camera-Facing Cards and Pixel Footprint 0.075; clear Projection Camera to follow the current camera. Lower Minimum Opacity to at most 1/255, retaining a smaller existing threshold. Starts an update; Undo supported. |
| Set Redshift Detail Quality | Raise transparency depth to at least 128, Unified Min Samples to 16 and Max Samples to 128. Disables Automatic Sampling so these floors take effect; sets adaptive thresholds to at most 0.01. Keeps stricter existing settings. Changes the current document only on explicit use; Undo supported. Can increase render time. |
| Create Estimated Source Camera | Create an editable camera from new AI metadata in adjacent `generation.json`. It is an estimate for square `prepared.png`, not calibrated photo reconstruction. Does not replace the active camera. |

The detail preset matches the new-object quality profile and can use more time and memory than an intentionally reduced import limit. SH3 evaluates only coefficients actually present in the file; it does not add SH to an SH0 model. The preset does not modify the source file or the document's display transform. Use **Set Redshift Detail Quality** separately to change render depth and sampling.

**Status** reports retained / source splat counts and their percentage. The limit is now **3,000,000**; scans exceeding it after opacity filtering still use a deterministic sample. The tested `Raspberry.sog` contains approximately 2.37 million splats: at Minimum Opacity 1/255, 2,309,943 pass the filter (97.4% of the source). The 3-million limit retains all of those eligible splats without reservoir sampling; the remainder is removed by the opacity threshold. The preset cannot synthesize missing hair, hidden geometry or reflections. Polygon-card compositing, transparency and colour management differ from a native Gaussian renderer, so identical appearance is not guaranteed.

## LOOK

| Control | Meaning |
| --- | --- |
| Colour Management | **sRGB Source to Scene Linear:** decode sRGB source colour, respecting explicit linearRGB metadata. **Treat Source as Linear:** skip sRGB decoding. Then convert to the document working space using native OCIO. The document's view transform/exposure still applies. |
| Highlight Limit | Upper RGB limit after colour correction. Values above 1 preserve HDR values. |
| SH Strength | Scale the non-constant, view-dependent part of SH. Does not change the base SH0 colour. |
| Emission Weight | Self-lit colour contribution. 1 with Diffuse/SSS 0 is useful for preserving scan colours. |
| Diffuse Weight | Response to scene lighting. Use with lights when you want the object to interact with the scene. |
| Subsurface Weight | Thin-walled diffuse transmission on these flat cards. Try a light behind the model. This is not a solid volume skin shader. |

Weights are stored per object in vertex maps, so separate objects can share the material and still animate different weights. Weight-only edits reuse geometry, normals and colour. Redshift accumulation restarts independently of the plugin's CPU update.

## Colour Correct

| Control | Neutral | Meaning |
| --- | --- | --- |
| Gamma | 1 | Adjust midtone response. |
| Contrast | 0.5 | Increase or decrease colour contrast. |
| Hue (degrees) | 0 | Rotate hue; the unit is degrees. |
| Saturation | 1 | Colour intensity; 0 removes saturation. |
| Level | 1 | Multiply colour levels. |

Colour correction reuses the geometry but still processes each loaded splat. Large scans cost more CPU time.

Interactive updates start after **0.6 seconds without changes**. The last complete model remains visible while you drag a slider or orbit a camera. If only the camera changes during a calculation, that calculation finishes and the latest requested view is processed next; intermediate views are not each queued as separate jobs. Changing source data or other preparation settings can cancel obsolete work. Ordinary updates stay in Status and can be stopped with Cancel Processing.

Camera movement does not recalculate SH0 colours. With Camera-Facing Cards off, a view change updates only colour when the file has active view-dependent SH; otherwise it needs neither a colour nor a geometry pass. Camera-facing projection still requires new geometry. Final render/export evaluates the requested camera and settings without the 0.6-second interface delay, reusing matching prepared data where available.

## Viewport

| Control | Meaning |
| --- | --- |
| Point Preview | Draw lightweight coloured points in the editor. Redshift IPR and final rendering still receive the full loaded card geometry. |
| Preview Points (0 = All) | Limit editor point drawing only. 0 draws all loaded points, after Maximum Splats and opacity filtering. Does not lower full-geometry memory usage. |

For large scans, keep **Point Preview on** and start with **10,000 Preview Points**. Use fewer preview points if drawing is slow. Camera-Facing Cards off avoids geometry updates on camera movement. Maximum Splats controls render-geometry memory and preparation cost; Preview Points controls only editor drawing. Parsing still validates the whole source file, so multi-million-splat files need time on their first load.

The C4D plugin keeps binary Gaussian PLY source records packed when **Maximum Splats is above 262,144**. Prepared positions, card axes, normals and colours use compact float64 buffers for native plugin operation. Separate test fixtures measured about **88% less retained Python source-cloud memory** and **82.8% less retained prepared-buffer memory**. These are component measurements, not a reduction promised for the entire Cinema 4D process: native polygon geometry, materials and renderer memory still matter.

## Advanced and motion

| Control | Meaning |
| --- | --- |
| Global Scale | Scale the whole model. |
| Pixel Footprint (variance; 0 = Off) | Image-space filtering for perspective Camera-Facing Cards. Default 0.075 preserves a small footprint for thin details; 0 disables filtering. Range 0–2, step 0.025. Higher values broaden the projected splats and can soften detail. |
| Splat Scale | Change card sizes without moving their centres. Oversizing can blur details; undersizing can create holes. |
| Maximum Splats | Retain up to this many opacity-eligible splats; above the limit, take a deterministic uniform sample across the input file. Default and maximum 3,000,000; this retains existing splats rather than generating new ones. Loading/filter changes queue a new load after changes settle; Initialise / Reload starts it immediately. |
| Minimum Opacity | Discard nearly transparent splats on load. Default 1/255 (about 0.00392157). Lower values retain fine details but may increase memory/render work. |
| Opacity Multiplier | Scale the opacity of retained splats. |
| Flip Y Axis | Reflect Y along with the Gaussian covariance. AI results enable this to stand upright in C4D. |
| Redshift Material | Editable node-material link. |
| Create MoGraph Fracture Rig | Create a native Fracture in Explode Segments mode. Each card is a segment; add effectors to the Fracture. Point Preview is disabled for this rig. Existing object PSR tracks retain their coordinate system. |
| Status | Current operation, final result or useful error text. Remains available after the progress window closes. |
| Support the author - Boosty | Optional support link below Status. Opens the author's Boosty page in your default browser only when clicked. The plugin remains free. |

SH and camera-facing calculations occur before deformers/effectors, not separately for each deformed segment or reflected ray.

**Pixel Footprint** adds variance measured in pixel squared to the projected Gaussian shape. Use Camera-Facing Cards with a perspective camera, start at **0.075**, and compare fine edges at the intended final resolution. Camera pose, lens, output resolution and pixel aspect affect the result. The filter uses render-output settings, not the viewport window's size. Other C4D camera projection types keep the previous card path. This can preserve thin features that already exist in the loaded splats; it adds no artificial fur and cannot recover splats removed by sampling or opacity filtering.

## Moving a project

Use **Save Project with Assets** for the source scan, selected image and converted PLY cache. Copy the **whole numbered sequence** separately if other frames will be used. Copy adjacent **`generation.json`** manually to preserve estimated-camera creation. Keep different source filenames unique in the same project; generated outputs already get unique suffixes.

The procedural object needs the plugin on the other machine. Make Editable produces polygon cards; its OSL material code is stored in the scene. The original scan is still worth keeping for later edits.

## Comparing with a Gaussian viewer

A scan stores positions, covariance, opacity and optional SH coefficients. Website camera poses, post effects, colour blending and renderer settings are separate from that data. The plugin does not extract a website scene from a SOG file.

Compare completed renders at the same resolution and camera. Point Preview is deliberately sparse and does not show the render geometry. Source Fidelity retains all eligible records up to its cap and uses a 0.075 actual-pixel variance; this corresponds to a 0.3 covariance ridge in doubled projection coordinates. Larger footprint values can make tiny bright splats look like broad dots.

Redshift blends scene-linear material colours and traces polygon cards. A Gaussian viewer can blend encoded colours and use a different alpha kernel, sorting and sharpening. Decoding sRGB correctly does not make those pipelines identical; the former “Match Splat Viewer” label has been replaced to avoid that implication. No one-to-one rendering claim is made.
