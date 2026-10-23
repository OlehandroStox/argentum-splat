<p align="center"><img src="docs/media/icon.png" width="88" alt="Argentum Splat icon"></p>

<h1 align="center">Argentum Splat</h1>
<p align="center"><strong>Images to 3D Gaussian splats. Inside Cinema 4D.</strong><br>Free, open-source integration for Cinema 4D 2027 and Redshift on Windows.</p>
<p align="center">
  <a href="https://github.com/OlehandroStox/argentum-splat/releases/download/v0.7.2/ArgentumSplat-0.7.2-C4D2027-Windows.zip">Download 0.7.2</a> ·
  <a href="#install">Install</a> ·
  <a href="docs/controls.md">Controls</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="https://boosty.to/olehandrostox/donate">Support the author</a> ·
  <a href="https://github.com/OlehandroStox/argentum-splat/issues">Help & feedback</a>
</p>

![Cinema 4D 2027](https://img.shields.io/badge/Cinema_4D-2027-7367F0)
![Windows x64](https://img.shields.io/badge/Windows-x64-169FC6)
![MIT integration](https://img.shields.io/badge/Integration-MIT-55B98C)
![Preview release](https://img.shields.io/badge/Status-experimental_preview-E8AE54)

Generate a static 3D Gaussian model from one image with **local TripoSplat inference**, or load an existing Gaussian scan. Adjust its appearance, render it with Redshift, and use Cinema 4D deformers and MoGraph.

> **Preview release:** version 0.7.2 uses development plugin IDs `1000007–1000009`, not registered permanent Maxon IDs. They can conflict with another plugin using those IDs. Test in a separate C4D preferences folder before production use. [Details and compatibility](docs/installation.md#plugin-ids).

## Current release: 0.7.2

**Known first-view limitation:** the five-file native test found that an interior church scan loads but its automatic exterior overview is unusable. The 4-million cap also reduces larger sources. Automatic framing is an overview helper, not a guarantee that every scan opens at its authored viewpoint. [Actual test results](docs/validation.md#072-five-real-sog-imports-with-untouched-model-defaults).

**[Download the Windows ZIP](https://github.com/OlehandroStox/argentum-splat/releases/download/v0.7.2/ArgentumSplat-0.7.2-C4D2027-Windows.zip)** · [Release notes](https://github.com/OlehandroStox/argentum-splat/releases/tag/v0.7.2)

- **SOG orientation:** new objects convert conventional Y-down SOG coordinates to Cinema 4D Y-up before framing. Saved older scenes retain their orientation; an Advanced override handles pre-oriented sources.
- **Less work on large scans:** build native geometry only for nonzero projected cards of standalone objects, retaining all imported source records. Hierarchies keep stable per-source indexing for MoGraph. Decode only the attributes needed by each pass.
- **Latest camera wins:** after a short settling interval, stop obsolete view arithmetic and reuse the parsed scan for the latest view. Do not publish an obsolete view as the new ready model. Large updates are still not instantaneous.
- **Automatic first view:** in an otherwise empty scene, fit an editable camera to a small model or large scan. Reuse matching AI source-camera metadata when available. Existing scene cameras and hand-edited import cameras stay unchanged.
- **Frame Loaded Scan:** create a separate fitted camera on demand. Source Summary reports loaded/source counts, SH data, opacity filtering and import-limit sampling.
- **Large-scene projection:** behind-camera splats collapse safely, screen-space bounds prevent near-camera background streaks, and Pixel Footprint 0 retains perspective projection.
- **Automatic Redshift preparation:** new objects prepare transparency depth and sampling once per new source, with an opt-out checkbox. Later camera/LOOK edits preserve manual render settings.
- **Quality by default:** new objects retain up to 4 million splats at a 1/255 opacity threshold, with captured-colour lighting, full available SH and perspective filtering. Existing scene values stay intact.
- **Quiet updates:** camera and LOOK changes reuse loaded data and update in the background; initial loads and explicit reloads retain progress and Cancel.
- **Source Fidelity:** full available SH, up to 4 million splats, unlit captured colour and perspective pixel filtering for thin details. This remains a Redshift card approximation.
- **Lower Python memory:** binary Gaussian PLY records stay packed when Maximum Splats exceeds 262,144; native plugin preparation uses compact float64 geometry and colour buffers.
- **Automatic setup:** run `Install.cmd` to install the plugin, private Python, extra-format converter and AI dependencies. Ready components are reused on repeat runs.
- **Responsive SCAN loading:** this release includes background preparation, a progress window with Cancel, and staged geometry assembly. The previous complete model stays visible until its replacement is ready.
- **Less repeated work:** LOOK weight edits reuse geometry. With Camera-Facing Cards off, camera movement reuses spatial data and updates SH colours as needed; moving lights does not reload the source file.
- **Checked for motion design:** native Fracture + Plain Effector and Bend were tested across 13 frames, alongside camera/light changes and Redshift previews.

Validated with **222 portable tests on Python 3.10 and 3.12**, plus native cache/update checks in Cinema 4D 2027. Separate fixtures measured about **88% less retained Python source-cloud memory** and **82.8% less retained prepared-buffer memory**; these are not whole-process RAM savings or real-time guarantees. Earlier installation checks include real image-to-3D generation in a fresh Python 3.12 environment. Large scans still take time to load; Camera-Facing Cards intentionally rebuild orientation. See the [validation scope](docs/validation.md) for test conditions and limits.

For the tested **`Raspberry.sog`** (approximately 2.37 million splats), the 4-million limit keeps all **2,309,943** splats passing the 1/255 opacity threshold: **97.4% of the source**, without additional reservoir sampling. The remaining splats are opacity-filtered. Larger files can still be sampled, and the Redshift card result is not guaranteed to match a native Gaussian renderer exactly.

## See the result

| One input image | Redshift output in Cinema 4D |
| --- | --- |
| <img src="docs/media/house-input.png" width="360" alt="Single input image of a miniature stone courtyard house"> | <img src="docs/media/redshift-front.png" width="480" alt="House Gaussian model rendered by Argentum Splat in Cinema 4D with Redshift"> |

![Turntable of the generated house Gaussian model, rendered by a reference Gaussian compositor rather than Redshift](docs/media/house-orbit.gif)

**One generated model, multiple views.** This turntable reads the exported PLY with a reference Gaussian compositor; it is **not a Cinema 4D screen recording**. The still image above is an actual Redshift render. Different compositing and view transforms produce different appearances. Input example: TripoSplat / VAST AI Research. [Asset credits and settings](docs/media/README.md).

## What it does

| Feature | What you get |
| --- | --- |
| **Image → 3D** | One image → `.ply` and `.splat`, automatically loaded into a procedural C4D object. Background removal included. |
| **Import scans** | PLY, SPLAT, SPZ; bundled SOG and KSPLAT through the optional local converter. |
| **Video / sequence input** | Pick and preview one frame, then generate one static model from it. |
| **Redshift rendering** | Elliptical Gaussian-opacity cards, editable node material, emission/diffuse/transmission controls. |
| **Colour & view dependence** | Gamma, contrast, hue, saturation, level; SH1–SH3 view-dependent colour when present in the scan. |
| **Detail tools** | Automatic initial framing and Redshift preparation, Source Summary, Source Fidelity preset and editable overview/source cameras. |
| **Motion design** | Native deformable geometry and a MoGraph Fracture rig for per-splat effectors. |
| **Responsive workflow** | Background SCAN loading, batched C4D assembly, cached LOOK/orbit updates, point preview and progress with Cancel. |

Your media stays local. Initial setup downloads dependencies and model weights; subsequent inference runs offline. No paid API key or plugin subscription is required. Cinema 4D and Redshift are separate products.

## Install

1. Download **[ArgentumSplat-0.7.2-C4D2027-Windows.zip](https://github.com/OlehandroStox/argentum-splat/releases/download/v0.7.2/ArgentumSplat-0.7.2-C4D2027-Windows.zip)**. This is the installer package; GitHub's automatic “Source code” archive is intended for development.
2. Extract the ZIP, close Cinema 4D and run **`ArgentumSplat/Install.cmd`**. It installs the plugin, extra-format converter, private Python runtime and AI dependencies automatically. If several C4D preferences folders exist, choose the one you use.
3. Wait for the setup summary, then start C4D → **Extensions → ArgentumSplat → Argentum Splat**.

**No manual Python installation is needed.** Setup keeps a working existing AI environment, or downloads a private Python **3.12.15** with a verified checksum. It needs no administrator rights and does not change system PATH or C4D's Python. The first setup needs internet access, several GB of storage/downloads and time; subsequent runs reuse ready components. The in-plugin **Set Up AI / Extra Formats** button uses the same automatic setup.

**Requirements:** Windows x64 + Cinema 4D **2027**. Redshift for rendering. Local AI needs an NVIDIA **Ampere-or-newer BF16-capable CUDA GPU** and a compatible NVIDIA driver. Setup checks the GPU before large AI downloads; it does not install drivers. A separate CUDA Toolkit is not needed. Tested on RTX 4070 12 GB. Native PLY/SPLAT/SPZ v2/v3 import works without AI, and an AI setup failure keeps the installed plugin available. macOS, AMD inference and older C4D versions are not supported by this release.

[Installation details, manual setup and troubleshooting →](docs/installation.md)

## Your first model

After the initial runtime download:

1. Select an image in **Input File**. Start with one clear, fully visible object.
2. Use **65,536 Gaussians**, **20 steps**, **Alpha Erosion = 0** for a first test.
3. Click **Load / Generate from Input**. The progress window shows the current stage; **Cancel** stops background work.
4. New objects already use **Source Fidelity** settings. **Auto Frame in Empty Scene** creates a fitted camera on first load in an otherwise empty scene. In an existing scene, use your camera or click **Frame Loaded Scan** for a separate overview. For an older object, **Source Fidelity – Preserve Detail** applies the quality preset explicitly.
5. Start rendering in **RS Render View**. **Auto Prepare Redshift on Import** sets transparency depth and sampling for each new source. Turn it off to keep full manual control; **Set Redshift Detail Quality** remains available for an explicit reset.

Generation time depends on the GPU, image and settings. The house example used 65,536 Gaussians, 20 steps, seed 42 and about 45 seconds of AI processing on an RTX 4070; loading and rendering take additional time.

### Better quality without guessing

- **Gaussian Count:** 65,536 / 131,072 / 262,144 are convenient presets within TripoSplat's model limit. More splats can retain finer detail but cost more memory and processing; they do not guarantee a better reconstruction.
- **Generation Steps:** begin at 20. Try 30–40 and compare; more steps are not a substitute for a good source image.
- **Seed:** changes the inferred geometry. Keep it fixed to compare settings.
- **Alpha Erosion:** keep 0 for fine edges; higher values can remove fringes, whiskers and fine silhouette details.
- **Ready-made scans:** Gaussian Count does not resample an imported scan. Use **Maximum Splats** to control its loaded size.

[Every control, explained →](docs/controls.md)

## Supported inputs

| Input | Support |
| --- | --- |
| Images | PNG, JPG/JPEG, WebP, TIF/TIFF, BMP, TGA, GIF. Alpha is respected. |
| Gaussian data — native | Standard Gaussian PLY (ASCII / binary LE / BE), 32-byte SPLAT, gzip SPZ v2/v3. RGB point-cloud PLY gets estimated point sizes. |
| Gaussian data — converter | Bundled SOG, KSPLAT, SPZ v4 and packed PlayCanvas PLY via pinned PlayCanvas `splat-transform`. |
| Video | MP4, MOV, M4V, MKV, AVI, WebM, MPG/MPEG, MTS/M2TS, subject to available PyAV/FFmpeg codecs. |
| Sequences | Numbered image files; selected `shot_0100.png` + offset `2` uses `shot_0102.png`. Missing numbers are reported. |

**Video means one selected frame → one static model.** There is no multi-view training, photogrammetry or animated 4D reconstruction. EXR/HDR, HEIC/RAW, unbundled SOG, streamed/LOD scenes, LCC, SH4 and 2DGS are not claimed.

## What to expect

- These are **Gaussian splats**, not a watertight mesh for printing, CAD or character rigging. Make Editable produces polygon cards.
- Redshift uses a **Gaussian-card approximation**, not a custom native Gaussian rasterizer. Transparency, lighting and colour management affect the result.
- Single-image TripoSplat predicts unseen sides and outputs **SH0**. It does not create a physical hair groom or glass cornea, and cannot match every high-detail multi-view scan.
- Imported SH1–SH3 changes colour with the view; it is not ray-traced reflection. View-dependent evaluation happens before deformers/effectors.
- Point Preview reduces viewport drawing work, **not the memory needed for the full render geometry**. Maximum Splats is capped at 4,000,000; native geometry and renderer memory can still be substantial despite compact Python buffers.
- Weight edits reuse geometry; colour correction still visits the loaded splats. Camera-Facing Cards rebuilds card orientation when the camera moves. Redshift must converge again after changes to the scene.
- Repeated Redshift previews and render evaluation were checked; this release's live RS Render View start/stop cycle was not verified. These checks do not guarantee real-time performance on large scans or MoGraph rigs.

## Development & feedback

The portable test suite covers parsers, geometry, colour, source-camera metadata, media frame selection, input routing and progress parsing. Run:

```sh
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

These tests do not launch Cinema 4D or prove native Redshift rendering. Native checks were performed separately in C4D 2027.0.0 on Windows. [Validation scope](docs/validation.md) · [Changelog](CHANGELOG.md) · [Contributing](CONTRIBUTING.md).

Found a bug? [Open an issue](https://github.com/OlehandroStox/argentum-splat/issues/new/choose) with the plugin/C4D/Redshift versions, input format and the Status message. Remove personal paths and private images from logs before sharing.

## Support the project

**[☕ Support the author on Boosty](https://boosty.to/olehandrostox/donate)**

The same optional link is available inside the plugin: **Status → Support the author - Boosty**. It opens only when clicked.

Argentum Splat is free. If it saves you time, an optional tip helps support development. No donation is required to download or use this release. A star, a useful bug report, or an example made with the plugin also helps others find it. You can credit **Argentum Splat for Cinema 4D** and link this repository when sharing your work.

## License & credits

The independently written integration is **[MIT licensed](LICENSE)**. The local AI pipeline uses **[TripoSplat](https://github.com/VAST-AI-Research/TripoSplat)** by Tripo AI / VAST AI Research. Format conversion uses **[PlayCanvas splat-transform](https://github.com/playcanvas/splat-transform)**; SPZ follows **[Niantic's format](https://github.com/nianticlabs/spz)**.

Model weights and dependencies are downloaded separately and retain their own terms. **Built with DINOv3**; DINOv3 has a custom Meta license. The FLUX.2 autoencoder is Apache-2.0. Read the [third-party notices](ArgentumSplat/backend/THIRD_PARTY_NOTICES.md) and [converter notices](ArgentumSplat/backend/formats/THIRD_PARTY_NOTICES.txt).

Maintained by [OlehandroStox / ARGENTUM](https://github.com/OlehandroStox). Independently developed; not affiliated with Maxon.

License audit: [conditions for sharing and voluntary support](ArgentumSplat/LICENSE_SCOPE.md) · [dependency inventory and findings](docs/licenses/README.md).
