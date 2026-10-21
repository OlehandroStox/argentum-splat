# Controls

[Back to README](../README.md) · [Русский](controls.ru.md)

Labels match the plugin's English interface. Decimal LOOK controls increment by **0.1**; type a value for finer precision. Minimum Opacity increments by **0.001**. Existing values and animation keys are not rounded.

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

The progress window reports real stages, available percentages and elapsed time. Setup/conversion stages without a measurable total show activity, not a fabricated percentage. Synchronous C4D geometry construction may briefly block the editor and is not cancelled by the background-worker button.

## Scan and detail

| Control | Meaning / when to use it |
| --- | --- |
| Splat File | Direct source path for an existing scan. Use Initialise / Reload after changing it. The unified Input File is an alternative. |
| View-Dependent Colour | Evaluate up to SH1, SH2 or SH3 if the file contains those coefficients. Off keeps the base colour. TripoSplat outputs SH0, so its SH controls are unavailable. |
| Camera-Facing Cards | Project the Gaussian covariance into the selected camera plane. Off uses the two largest Gaussian axes for each card. Camera-facing mode needs extra work as the camera moves. |
| Projection Camera | Explicit camera for SH and camera-facing cards. Empty uses the render camera, falling back to the editor camera. |
| SPZ: Unconverted Coordinates | Keep SPZ's source RUB coordinates. Normally position, rotation and SH are converted together. Flip Y is applied afterward. |
| Normal Smoothing Passes | 0 disables; 1–8 averages nearby normals with aligned orientation. Does not blur the positions. |
| Initialise / Reload | Re-read the file, invalidate caches and create/update the material. It does not rerun AI. |
| Source Fidelity – Preserve Detail | Set Emission 1, Diffuse 0, Subsurface 0; enable camera-facing cards; clear Projection Camera; lower Minimum Opacity to at most 1/255. Keeps smaller thresholds. Undo supported. |
| Set Redshift Detail Quality | Raise transparency depth to at least 128, Unified Min Samples to 16 and Max Samples to 128. Keeps higher existing settings. Changes the current document only on explicit use; Undo supported. Can increase render time. |
| Create Estimated Source Camera | Create an editable camera from new AI metadata in adjacent `generation.json`. It is an estimate for square `prepared.png`, not calibrated photo reconstruction. Does not replace the active camera. |

The detail preset preserves the information already in a model. It cannot synthesize missing hair, hidden geometry or reflections.

## LOOK

| Control | Meaning |
| --- | --- |
| Colour Management | **Match Splat Viewer:** decode sRGB source colour, respecting explicit linearRGB metadata. **Treat Source as Linear:** skip sRGB decoding. Then convert to the document working space using native OCIO. The document's view transform/exposure still applies. |
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

## Viewport

| Control | Meaning |
| --- | --- |
| Point Preview | Draw lightweight coloured points in the editor. Redshift IPR and final rendering still receive the full loaded card geometry. |
| Preview Points (0 = All) | Limit editor point drawing only. 0 draws all loaded points, after Maximum Splats and opacity filtering. Does not lower full-geometry memory usage. |

## Advanced and motion

| Control | Meaning |
| --- | --- |
| Global Scale | Scale the whole model. |
| Splat Scale | Change card sizes without moving their centres. Oversizing can blur details; undersizing can create holes. |
| Maximum Splats | Deterministic uniform sample across the input file. Default 262,144; maximum 1,000,000. Reload to apply loading/filter changes. |
| Minimum Opacity | Discard nearly transparent splats on load. Lower values retain fine details but may increase memory/render work. |
| Opacity Multiplier | Scale the opacity of retained splats. |
| Flip Y Axis | Reflect Y along with the Gaussian covariance. AI results enable this to stand upright in C4D. |
| Redshift Material | Editable node-material link. |
| Create MoGraph Fracture Rig | Create a native Fracture in Explode Segments mode. Each card is a segment; add effectors to the Fracture. Point Preview is disabled for this rig. Existing object PSR tracks retain their coordinate system. |
| Status | Current operation, final result or useful error text. Remains available after the progress window closes. |
| Support the author - Boosty | Optional support link below Status. Opens the author's Boosty page in your default browser only when clicked. The plugin remains free. |

SH and camera-facing calculations occur before deformers/effectors, not separately for each deformed segment or reflected ray.

## Moving a project

Use **Save Project with Assets** for the source scan, selected image and converted PLY cache. Copy the **whole numbered sequence** separately if other frames will be used. Copy adjacent **`generation.json`** manually to preserve estimated-camera creation. Keep different source filenames unique in the same project; generated outputs already get unique suffixes.

The procedural object needs the plugin on the other machine. Make Editable produces polygon cards; its OSL material code is stored in the scene. The original scan is still worth keeping for later edits.
