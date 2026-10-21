<p align="center"><img src="docs/media/icon.png" width="88" alt="Argentum Splat icon"></p>

<h1 align="center">Argentum Splat</h1>
<p align="center"><strong>Images to 3D Gaussian splats. Inside Cinema 4D.</strong><br>Free, open-source integration for Cinema 4D 2027 and Redshift on Windows.</p>
<p align="center">
  <a href="https://github.com/OlehandroStox/argentum-splat/releases">Download</a> ·
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

> **Preview release:** version 0.3.2 uses development plugin IDs `1000007–1000009`, not registered permanent Maxon IDs. They can conflict with another plugin using those IDs. Test in a separate C4D preferences folder before production use. [Details and compatibility](docs/installation.md#plugin-ids).

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
| **Detail tools** | Source Fidelity preset, explicit Redshift quality setup, estimated source camera for new AI results. |
| **Motion design** | Native deformable geometry and a MoGraph Fracture rig for per-splat effectors. |
| **Responsive workflow** | Point preview, geometry reuse for LOOK edits, 0.1 slider increments, progress window with Cancel. |

Your media stays local. Initial setup downloads dependencies and model weights; subsequent inference runs offline. No paid API key or plugin subscription is required. Cinema 4D and Redshift are separate products.

## Install

1. Download **`ArgentumSplat-0.3.2-C4D2027-Windows.zip`** from [Releases](https://github.com/OlehandroStox/argentum-splat/releases). Choose the named asset, not GitHub's automatic “Source code” archive.
2. Extract the ZIP. Close Cinema 4D and run **`ArgentumSplat/Install.cmd`**. Or copy the whole `ArgentumSplat` folder into the `plugins` folder inside your C4D 2027 preferences directory.
3. Start C4D → **Extensions → ArgentumSplat → Argentum Splat**.
4. For image/video generation, click **Set Up AI / Extra Formats** once. Wait for **Status** to report completion.

**Requirements:** Windows x64 + Cinema 4D **2027**. Redshift for rendering. Local AI additionally needs Python **3.10–3.12**, an NVIDIA **Ampere-or-newer BF16-capable CUDA GPU**, and several GB of downloads. Tested on RTX 4070 12 GB. Importing native PLY/SPLAT/SPZ v2/v3 does not require the AI models. macOS, AMD inference and older C4D versions are not supported by this release.

[Installation details, manual setup and troubleshooting →](docs/installation.md)

## Your first model

After the initial runtime download:

1. Select an image in **Input File**. Start with one clear, fully visible object.
2. Use **65,536 Gaussians**, **20 steps**, **Alpha Erosion = 0** for a first test.
3. Click **Load / Generate from Input**. The progress window shows the current stage; **Cancel** stops background work.
4. When loading finishes, click **Source Fidelity – Preserve Detail** to preserve the source colours. Frame the object with your render camera.
5. Start rendering in **RS Render View**. If overlapping splats look incomplete, use **Set Redshift Detail Quality**; it raises transparency depth and sampling and can increase render time.

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
- Point Preview reduces viewport drawing work, **not the memory needed for the full render geometry**. Maximum Splats is capped at 1,000,000 in this Python implementation.
- Weight edits reuse geometry; colour correction still visits the loaded splats. Redshift must then converge again.

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
