# Controls

## In-app Help and simpler panels

**Image** accepts one still picture; **Photos** reconstructs one scan from overlapping views in a folder; **Scan** imports existing Gaussian files. For Photos use Set Up Photos once, then Reconstruct from Photos.

## Import quality

New objects use **MAX — Full Source** automatically. Choose a lower **SCAN → Import Quality** for a faster draft. The optional large-file choice window is disabled by default.

| Preset | Retained splats, before opacity filtering |
| --- | ---: |
| LOW | Up to 250,000 |
| MEDIUM | Up to 1,000,000 |
| HIGH | Up to 4,000,000 |
| MAX — Full Source (default) | All opacity-eligible source splats |

**Import Budget** reads the source count without loading the geometry and shows the selected upper bound and an approximate additional RAM range. It is not a VRAM measurement. If the estimated allocation exceeds available RAM, loading stops with an explanation; MAX is never silently reduced. **Ask for Large Files** remembers its setting per object. Cancel closes the choice without starting heavy work; processing also retains its progress/Cancel window and the previous complete model.

These presets control the existing **Maximum Splats** setting: **0 means Full Source**. A manually entered limit appears as CUSTOM. Saved objects keep their limits. **Source Fidelity** now preserves the chosen import budget. **SH 1–3** controls stored view-dependent colour; **Preview Points** controls editor drawing only. Neither replaces Import Quality. The parser still validates the whole source, so LOW does not make reading a large file instant. MAX needs enough memory for the full source.


[Back to README](../README.md) · [Русский](controls.ru.md)

The Help footer shows the installed version and a Boosty button. Open Help Reader provides a resizable reading window.

Labels match the plugin's English interface. Decimal LOOK controls increment by **0.1**; type a value for finer precision. Minimum Opacity increments by **0.001**. Existing values and animation keys are not rounded.

## New-object defaults

New objects start with **Source Fidelity**: Maximum Splats **0 (Full Source)**, Minimum Opacity **1/255 ≈ 0.00392157**, Camera-Facing Cards **on**, Pixel Footprint **0.075**, SH degree **3**, SH Strength **1**, Normal Smoothing **0**. LOOK starts with **sRGB Source to Scene Linear**, Highlight Limit **3**, Emission **1**, Diffuse **0**, Subsurface **0**. Global Scale **100**, Splat Scale **1** and Opacity Multiplier **1** remain unchanged.

**Existing and duplicated objects keep their saved values.** Apply Source Fidelity explicitly to an older object. It preserves colour correction, scale, axis conversion and a lower opacity threshold. The preset does not reset a deliberately chosen Colour Management mode.

Large imports and camera-facing updates need more time and RAM than a reduced scan. Point Preview starts at **50,000 points** for new objects; it only reduces editor drawing. For draft work, lower Maximum Splats or turn Camera-Facing Cards off, accepting reduced detail or projection accuracy. Choose HIGH or MAX for final retention; Source Fidelity preserves that choice. Gaussian Count controls AI generation separately; the import limit does not create extra Gaussians.

## Input

| Control | Meaning / when to use it |
| --- | --- |
| Image File | One still picture. |
| Preview Image | Read the selected image and open it in C4D Picture Viewer before generation. |
| Gaussian Count | AI generation presets up to 1,048,576 and Custom. Custom Count accepts 32,768–1,048,576, in multiples of 32; 1,000,000 is valid. Values above 262,144 are experimental and outside the upstream recommended range; more points do not guarantee better reconstruction. |
| Generation Steps | AI sampling steps, 1–100. Default 20. More steps take longer and may not improve every input. |
| Seed | Random seed for the prediction. Keep fixed for comparisons; change to explore a different result. |
| Alpha Erosion | 0–8. Shrinks the alpha mask after background removal. Keep 0 for delicate edges; use a small value to remove a fringe. Applies only to the next generation. |
| Output Folder | Where generated files are saved. Default: `%LOCALAPPDATA%\ArgentumSplat\generated`. Each job has its own directory. |
| Generate from Image | Generate from one still picture. |
| Cancel Processing | Stop the background worker and its child processes. The progress window's Cancel and close button also cancel. |
| Set Up AI / Extra Formats | Install the isolated Python AI environment and the optional format converter. Requires internet during setup. |
| Open Output Folder | Open the output location in Explorer. |

Generation, conversion, initial scan loads, changed source/loading settings and explicit **Initialise / Reload** show a progress window with Cancel. It covers **SCAN reading, geometry preparation and C4D assembly**, showing the stage, available progress and elapsed time. Setup/conversion stages without a measurable total show activity. Ordinary camera and LOOK updates report progress in **Status** without opening this window; use **Cancel Processing** to stop them.

Scan reading/calculation runs in a worker; C4D geometry is assembled in short UI-thread batches. Cancellation keeps the previous complete model. A single native allocation/commit must finish before cancellation can take effect.

## Scan and detail

| Splat File | Direct source path for an existing scan. Loading is queued after changes settle; Initialise / Reload starts it immediately or retries a cancelled/failed request. |
| View-Dependent Colour | Evaluate up to SH1, SH2 or SH3 if the file contains those coefficients. Off keeps the base colour. TripoSplat outputs SH0, so its SH controls are unavailable. |
| Camera-Facing Cards | Project the Gaussian covariance into the selected camera plane. Off uses the two largest Gaussian axes for each card. Camera-facing mode needs extra work as the camera moves. |
| Projection Camera | Explicit camera for SH and camera-facing cards. Empty uses the render camera, falling back to the editor camera. Status warns when the override differs from the render camera; clear the link to follow camera switches. |
| SPZ: Unconverted Coordinates | Keep SPZ's source RUB coordinates. Normally position, rotation and SH are converted together. Flip Y is applied afterward. |
| Normal Smoothing Passes | 0 disables; 1–8 averages nearby normals with aligned orientation. Does not blur the positions. Perspective camera-facing cards already share one normal; their redundant smoothing pass is skipped. |
| Initialise / Reload | Load or refresh the scan with progress and Cancel. Unchanged source/settings reuse prepared data; file timestamp/size and loading settings invalidate the relevant caches. It does not rerun AI. |
| Source Fidelity – Preserve Detail | Preserve the import limit; set SH3 / SH Strength 1, Emission 1, Diffuse 0, Subsurface 0 and Normal Smoothing Passes 0. Enable Camera-Facing Cards and Pixel Footprint 0.075; clear Projection Camera to follow the current camera. Lower Minimum Opacity to at most 1/255, retaining a smaller existing threshold. Starts an update; Undo supported. |
| Auto Prepare Redshift on Import | On for new objects. Apply the Redshift depth/sampling floors once per source. On the first SOG or Photos import into an empty scene, replace the default ACES view with Un-tone-mapped to preserve captured colours. Existing scenes and custom views are preserved. The saved marker prevents later camera, LOOK and reload operations from resetting manual choices. Disable for full manual control. Lights, exposure and working colour space stay unchanged. Undo supported. |
| Auto Frame in Empty Scene | On for new objects. Once per new source, create a camera when this is the only scene object and no user camera/Projection Camera is selected. Fit robust source bounds and adapt the near clipping plane to size; use matching AI camera metadata when available. Reuse an untouched generated camera for a changed source. Existing scene content and hand-edited cameras block automatic reframing. Source geometry, units and axes stay unchanged. |
| Frame Loaded Scan | Create and activate a separate editable camera for the loaded model. Preserves earlier cameras. Starts a camera-dependent update using the parsed source; no file reread. |
| Set Redshift Detail Quality | Raise transparency depth to at least 128, Unified Min Samples to 16 and Max Samples to 128. Disables Automatic Sampling so these floors take effect; sets adaptive thresholds to at most 0.01. Keeps stricter existing settings. Changes the current document only on explicit use; Undo supported. Can increase render time. |
| Create Estimated Source Camera | Create an editable camera from new AI metadata in adjacent `generation.json`. It is an estimate for square `prepared.png`, not calibrated photo reconstruction. Does not replace the active camera; disabled without matching AI metadata. |

The detail preset matches the new-object quality profile and can use more time and memory than an intentionally reduced import limit. SH3 evaluates only coefficients actually present in the file; it does not add SH to an SH0 model. The preset does not modify the source file or the document's display transform. **Auto Prepare Redshift on Import** applies render depth and sampling once for each new source; the explicit **Set Redshift Detail Quality** button remains available.

## LOOK

| Control | Meaning |
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

| Point Preview | Draw lightweight coloured points in the editor. Redshift IPR and final rendering still receive the full loaded card geometry. |
| Preview Points (0 = All) | Limit editor point drawing only. 0 draws all loaded points, after Maximum Splats and opacity filtering. Does not lower full-geometry memory usage. |

For large scans, keep **Point Preview on** and start with the new default of **50,000 Preview Points**. Use fewer preview points if drawing is slow. Camera-Facing Cards off avoids geometry updates on camera movement. Maximum Splats controls render-geometry memory and preparation cost; Preview Points controls only editor drawing. Parsing still validates the whole source file, so multi-million-splat files need time on their first load.

## Advanced and motion

| Global Scale | Scale the whole model. |
| Pixel Footprint (variance; 0 = Off) | Image-space filtering for perspective and parallel Camera-Facing Cards. Default 0.075. Filtering broadens tiny splats and compensates their peak opacity for the added area; 0 disables both. Range 0–2, step 0.025. Higher values can soften detail. |
| Splat Scale | Change card sizes without moving their centres. Oversizing can blur details; undersizing can create holes. |
| Maximum Splats | Retain up to this many opacity-eligible splats; above the limit, take a deterministic uniform sample across the input file. Default 0 (Full Source); this retains existing splats rather than generating new ones. Loading/filter changes queue a new load after changes settle; Initialise / Reload starts it immediately. |
| Minimum Opacity | Discard nearly transparent splats on load. Default 1/255 (about 0.00392157). Lower values retain fine details but may increase memory/render work. |
| Opacity Multiplier | Scale the opacity of retained splats. |
| Auto SOG Orientation | Enabled for new objects. Map conventional SOG Y-down coordinates to Cinema 4D Y-up before fitting the first camera; transform shape and view-dependent colour consistently. Older saved objects may keep this disabled. Turn off for a source that was already reoriented. |
| Flip Y Axis | Reflect Y along with the Gaussian covariance. AI results enable this to stand upright in C4D. |
| Redshift Material | Editable node-material link. |
| Create MoGraph Fracture Rig | Create a native Fracture in Explode Segments mode. Each card is a segment; add effectors to the Fracture. Point Preview is disabled for this rig. Existing object PSR tracks retain their coordinate system. |
| Status | Current operation, final result or useful error text. Remains available after the progress window closes. |
| Support the author - Boosty | Optional support link below Status. Opens the author's Boosty page in your default browser only when clicked. The plugin remains free. |

SH and camera-facing calculations occur before deformers/effectors, not separately for each deformed segment or reflected ray.

**Pixel Footprint** adds variance measured in pixel squared to the projected Gaussian shape. Use Camera-Facing Cards with a classic or native Redshift perspective/parallel camera, start at **0.075**, and compare fine edges at the intended final resolution. Camera pose, lens, output resolution and pixel aspect affect the result. Film Offset/RS Sensor Shift also moves the visible frame used for culling. Parallel cameras use one SH viewing direction, including when Camera-Facing Cards is off. The filter uses render-output settings, not the viewport window's size. Fixed front/side, oblique and other uncalibrated projection types keep the previous card path. This can preserve thin features that already exist in the loaded splats; it adds no artificial fur and cannot recover splats removed by sampling or opacity filtering.

In **0.8.3**, filtered cards also receive an opacity factor based on the ratio of their original and filtered projected areas. This reduces excess brightness caused by expanding tiny bright splats, without changing their stored RGB or SH. Larger resolved splats are affected much less. Pixel Footprint 0 disables the correction together with filtering. Existing scenes with a nonzero filter can therefore look different after updating.

## Moving a project

Use **Save Project with Assets** for the source scan, selected image and converted PLY cache. Copy the **Photos Folder** separately to reconstruct again. Copy adjacent **`generation.json`** manually to preserve estimated-camera creation. Keep different source filenames unique in the same project; generated outputs already get unique suffixes.

The procedural object needs the plugin on the other machine. Make Editable produces polygon cards; its OSL material code is stored in the scene. The original scan is still worth keeping for later edits.

## Appearance and performance

A scan stores its shape, colour and transparency. Website cameras, backgrounds and post-effects are separate settings. Redshift uses polygon cards and may differ from a Gaussian viewer. Compare finished renders at the same camera and resolution.

The opacity profile introduced in 0.8.2 matches SuperSplat's normalized Gaussian falloff; 0.8.3 adds the filter-area compensation described above. Existing unmodified built-in shaders migrate; custom shader code is preserved. Linear-light compositing, finite transparency depth and close card intersections still limit visual parity. See [rendering compatibility](rendering-compatibility.md).

Camera-Facing Cards are prepared for one camera. For MoGraph movement across the frame, mirrors or secondary views, turn this option off to retain oriented cards, accepting less accurate projection. During an update, IPR can temporarily show the previous view; wait for **Ready** before judging the result.

HIGH retains up to 4 million splats; MAX keeps all that pass the opacity filter. Lower Import Quality to reduce memory and preparation time, or Preview Points to improve editor drawing. These controls affect different stages.

## Automatic framing and Source Summary

Automatic framing fits an overview around the main scan region. Long background tails affect neither its framing bounds nor source retention. For conventional SOG, detailed projected coverage near the source origin can select an interior starting view. Existing user cameras remain unchanged. This is a geometric estimate, not recovery of missing camera metadata.

**Source Summary** shows retained/source counts, SH degree, colour space and whether filtering or a load limit reduced the data. It does not rate reconstruction quality.

## Photos

PHOTOS — ONE SCAN FROM MULTIPLE VIEWS

Choose Photos Folder with pictures of one stationary subject. JPG, PNG, WebP, TIFF and BMP are accepted directly inside the folder; subfolders are ignored. Minimum 3, maximum 500. Start with 10–50 sharp overlapping views. Move the camera around the subject; keep subject and lighting still. Unrelated images, duplicates, blur, reflections, transparency and missing overlap can prevent alignment.

Set Up Photos downloads its separate private Python, PyCOLMAP and Brush (about 250 MB). Image AI weights are not required. CPU alignment, lens correction and GPU Gaussian training run locally. Photos are never uploaded. Brush needs a compatible GPU and current driver; memory depends on resolution and point count.

Training Steps defaults to 30,000. Maximum Gaussians defaults to 1,000,000: this is an upper limit, not a guaranteed result count. Photo Resolution is the longest side of processing copies; original photos are unchanged. Start with defaults and Reconstruct from Photos. Training progress shows elapsed time and target steps, not an invented percentage.

Cancel Processing stops the owned processes and keeps the previous scan. Each run has a new output folder. A completed PLY is imported if input selection is unchanged. alignment.json lists used and unused photographs: at least 60% and at least 3 must align. Partial alignment can leave holes. generation.json contains an estimated calibrated source view; scale is arbitrary. Copy it alongside the PLY when moving projects. Keep the original Photos Folder separately to reconstruct again.


## 0.9.1

Single Image predicts 3D from one picture. Multi-Photo Scan reconstructs observed surfaces from overlapping photographs. Captured View (0 = first) + Use Captured Camera activates one of the saved calibrated views. Keep capture-cameras.json and generation.json beside the PLY. Additional training cannot reconstruct unseen surfaces. Existing objects keep their saved training settings.

Help Reader contains the complete manual, author credit, live status, GitHub and Boosty. The Help tab is compact. Status appears in all plugin tabs. Redshift preparation activates a separate copy named Argentum Splat - Splatting Transparency and preserves the original preset.


## 0.9.2 — Photos colour

Training Colour: Redshift - Linear uses lossless 16-bit linear training copies. Splat Viewers - sRGB preserves conventional viewer output. Camera alignment uses display images. PLY embeds its colour space and Brush kernel profile; no manual import correction is needed. Existing sRGB scans need reconstruction for the full colour improvement.

For Photos scans, the default Pixel Variance automatically resolves to 0.3 to match the trainer; ordinary viewer scans retain 0.075. Explicit values other than the default are preserved. Increasing Maximum Gaussians alone does not guarantee sharper results. Fine detail also depends on processing resolution, calibration and overlapping coverage; test more than one photographed view and nearby camera positions.
