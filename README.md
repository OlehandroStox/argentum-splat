<p align="center"><img src="docs/media/icon.png" width="88" alt="Argentum Splat"></p>

<h1 align="center">Argentum Splat</h1>
<p align="center"><strong>Free Gaussian Splatting plugin for Cinema 4D 2027 and Redshift.</strong><br>Generate 3D from an image, import scans and work with them in Cinema 4D.</p>
<p align="center">
  <a href="https://github.com/OlehandroStox/argentum-splat/releases/download/v0.8.1/ArgentumSplat-0.8.1-C4D2027-Windows.zip"><strong>Download 0.8.1 for Windows</strong></a> ·
  <a href="#install">Install</a> ·
  <a href="README.ru.md">Русский</a> ·
  <a href="https://boosty.to/olehandrostox/donate">Support the author</a>
</p>

## See the result

| Input image | Cinema 4D / Redshift render |
| --- | --- |
| <img src="docs/media/house-input.png" width="360" alt="Miniature stone house input image"> | <img src="docs/media/redshift-front.png" width="480" alt="Generated house rendered with Argentum Splat in Redshift"> |

![Generated model viewed from different angles](docs/media/house-orbit.gif)

The still is a Redshift render. The turntable shows the exported model in a separate Gaussian viewer. [Media credits](docs/media/README.md).

## Features

- **Image to 3D:** local AI generation from a photo or a selected video/sequence frame.
- **Scan import:** Gaussian PLY, SPLAT, SPZ, SOG and KSPLAT.
- **Import Quality:** LOW, MEDIUM, HIGH or MAX, with a memory estimate before large imports.
- **Redshift:** editable material, colour correction and stored view-dependent colour.
- **MoGraph:** create a Fracture rig and use effectors on splat cards.
- **Convenient workflow:** point preview, cached updates, progress and cancellation.
- **Built-in Help:** English and Russian instructions, available offline.

Media is processed locally. No paid API key or plugin subscription is required.

## Install

1. [Download the ZIP](https://github.com/OlehandroStox/argentum-splat/releases/download/v0.8.1/ArgentumSplat-0.8.1-C4D2027-Windows.zip) and extract it.
2. Close Cinema 4D and run **ArgentumSplat/Install.cmd**. The installer sets up the plugin, private Python and required components.
3. Start Cinema 4D → **Extensions → ArgentumSplat → Argentum Splat**.

**Requirements:** Windows x64, Cinema 4D 2027 and Redshift. AI generation also needs an NVIDIA Ampere-or-newer GPU with BF16 support and a compatible driver. The first setup downloads several GB; manual Python installation is unnecessary. Importing existing scans does not require AI model weights.

[Installation options and troubleshooting](docs/installation.md).

## First steps

**From a photo or video:** choose a file in **INPUT**, optionally select a frame, then click **Generate from Image / Video**. Wait for **Ready** in Status and render with Redshift.

**From an existing scan:** choose it in **SCAN → Splat File** and select **Import Quality**. Start with HIGH; choose MAX to retain all splats that pass the opacity filter, if memory permits.

In an empty scene the plugin prepares Redshift and fits a camera automatically. For a scan added to an existing scene, use your camera or **SCAN → Manual Tools → Frame Loaded Scan**.

For control explanations, open **Help → Language / Язык** in the plugin, or read the [control guide](docs/controls.md). The installed version is shown at the bottom of Help.

## Useful to know

- Video and sequences provide **one frame for one static model**, not animated 3D or multi-view reconstruction.
- A Gaussian model is not a watertight polygon mesh. Redshift uses Gaussian cards, so its appearance can differ from other viewers.
- Large scans need more RAM and preparation time. **Preview Points** affects editor drawing; **Import Quality** affects loaded geometry.
- Automatic framing provides an overview. Interior scans may need a camera placed inside the captured area.

## Support and feedback

The plugin is free. If it helps your work, you can [support the author on Boosty](https://boosty.to/olehandrostox/donate), star the repository or [report a problem](https://github.com/OlehandroStox/argentum-splat/issues).

## License and credits

By [OlehandroStox / ARGENTUM](https://github.com/OlehandroStox). The integration is [MIT licensed](LICENSE). AI generation uses [TripoSplat](https://github.com/VAST-AI-Research/TripoSplat); format conversion uses [PlayCanvas splat-transform](https://github.com/playcanvas/splat-transform). Built with DINOv3. Dependencies and model components retain their [own licenses](ArgentumSplat/backend/THIRD_PARTY_NOTICES.md). Independent project; not affiliated with Maxon.
