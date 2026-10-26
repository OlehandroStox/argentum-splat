# Installation & troubleshooting

[README](../README.md) · [Русская быстрая установка](../README.ru.md#установка)

## Install the plugin

Download **ArgentumSplat-0.8.2-C4D2027-Windows.zip** from [Releases](https://github.com/OlehandroStox/argentum-splat/releases), extract it, and close Cinema 4D. Run `ArgentumSplat/Install.cmd` from the extracted folder. Do not run it inside the ZIP viewer.

The installer copies the plugin, sets up the extra-format converter, and prepares the private Python/AI environment and model weights. **You do not need to install Python or Node.js manually.** Choose your preferences folder if more than one C4D 2027 installation is found, then wait for the final summary. If no preferences folder exists yet, launch C4D 2027 once and close it before installing.

First setup needs internet access, several GB of free storage/downloads, and time. No administrator rights are needed. System PATH and Cinema 4D's embedded Python are left unchanged. Setup does not install Cinema 4D, Redshift or GPU drivers.

The stages report their own results. If AI setup fails, the copied plugin and a successfully installed format converter remain usable. Read the reported cause and rerun `Install.cmd` after resolving it. Ready components are reused instead of downloading everything again.

Restart C4D and choose **Extensions → ArgentumSplat → Argentum Splat**. Install only one copy in C4D's plugin search paths.

The installer backs up an existing plugin folder in `ArgentumSplat-backups` beside `plugins`. It does not change your startup layout. To add a toolbar icon, drag **Argentum Splat - Image to 3D** from **Customize Commands** to a palette and save your layout. The command is hidden from Extensions to avoid a duplicate menu entry.

## Installation modes

The default `Install.cmd` runs full setup. Advanced users can run these commands from the extracted `ArgentumSplat` directory:

```powershell
# Plugin + scan-format converter; skip the image-generation AI environment.
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -ImportOnly

# Copy only the plugin; no dependency downloads.
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -CoreOnly

# Choose a specific existing C4D 2027 preferences directory.
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install.ps1 -PreferencesFolder "C:\path\to\Maxon Cinema 4D 2027_preferences"
```

`-CoreOnly` supports native Gaussian PLY, SPLAT and SPZ v2/v3 using C4D's built-in Python. `-ImportOnly` also prepares bundled SOG, KSPLAT, SPZ v4 and packed PlayCanvas PLY. Neither mode prepares AI image/video generation. The execution-policy option applies to that PowerShell process only.

## Manual copy

For a manual install, open C4D Preferences → **Open Preferences Folder**, close C4D and copy the whole `ArgentumSplat` directory into its `plugins` directory (create `plugins` if needed). The result should be:

```text
<Cinema 4D 2027 preferences>/plugins/
└── ArgentumSplat/
    ├── ArgentumSplat.pyp
    ├── argentum_splat/
    ├── backend/
    └── res/
```

After a manual copy, restart C4D. Click **Set Up AI / Extra Formats** to run the same automatic dependency setup; wait for Status to finish. Manual copying by itself does not download the AI environment or converter.

## Optional local AI

Use an NVIDIA Ampere-or-newer GPU with BF16 CUDA support and a compatible NVIDIA driver. Setup checks GPU/driver availability before downloading the AI packages. A separate CUDA Toolkit installation is not needed. Memory requirements depend on the input and chosen quality.

Setup uses a separate environment at `%LOCALAPPDATA%\ArgentumSplat\runtime`. A working existing Python 3.10–3.12 AI environment is retained. Otherwise, it downloads **CPython 3.12.15**, Astral `python-build-standalone` release **20261020**, with a pinned SHA-256 check, then creates the private environment. This is a third-party CPython build, not the Python Software Foundation's Windows installer. Its bundled licenses remain with the installed runtime. [Source and notices](../ArgentumSplat/backend/THIRD_PARTY_NOTICES.md).

Initial downloads also include PyTorch CUDA wheels and multiple model checkpoints. Keep several GB available for downloads, environment and weights. Subsequent setup checks readiness and skips installation when components are ready. To recheck/install the AI dependencies and verify model files, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup_backend.ps1 -Repair
```

Advanced users can explicitly provide an existing compatible 64-bit Python with `setup_backend.ps1 -PythonExe "C:\path\to\python.exe"`; normal installation does not require this. The supported AI setup is Windows x64 / NVIDIA; CPU-only, AMD and macOS inference are not supported here.

## Optional extra formats

Bundled SOG, KSPLAT, SPZ v4 and packed PlayCanvas PLY use the PlayCanvas converter installed by full setup, `-ImportOnly`, or the combined setup button. Alternatively, run `setup_formats.ps1` from PowerShell. It uses a suitable Node 22+ installation or downloads the pinned official portable Node runtime. Files are converted locally; originals remain unchanged and the output is cached under `%LOCALAPPDATA%\ArgentumSplat\converted`.

Native Gaussian PLY, SPLAT and SPZ v2/v3 work without AI weights or the converter. Video/frame extraction needs the separate Python runtime with PyAV.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No Extensions entry | Restart C4D; check folder nesting and duplicate installs. Read C4D Console and `startup_error.log` if created beside the `.pyp`. A development-ID collision can prevent registration. |
| Setup reports a download error | Check the final summary and installer log, available storage and access to the download host. Rerun Install.cmd after resolving the issue; already ready components are reused. |
| Python missing / wrong Python version | The full installer supplies its own supported Python. Rerun the current Install.cmd or Set Up AI / Extra Formats; a system Python 3.13/3.14 does not need to be removed. |
| AI GPU/driver check fails | Use a supported NVIDIA GPU and compatible driver. Setup cannot add GPU capabilities or install the driver for you. The plugin can still import native scans; use ImportOnly to prepare extra scan formats without AI. |
| Black RS Render View | Confirm IPR is started, the render camera sees the model, and the object/material loaded successfully. Apply Source Fidelity for self-lit source colour. If data is loaded but layers disappear, inspect transparency depth or use Set Redshift Detail Quality. |
| Points in the viewport | Point Preview is enabled. It does not reduce Redshift output. Disable it to see cards in the editor. |
| SH sliders disabled | The file has no SH1–SH3 coefficients. Single-image TripoSplat results are SH0. |
| Video/sequence fails | Preview the selected frame. Frame index starts at 0; sequences use a filename offset. Missing frames, unsupported codecs and corrupt media report errors in Status. |
| SCAN load takes time | Progress covers reading, preparation and C4D assembly. First import validates all input records, even with Maximum Splats set lower. Cancel keeps the last complete model. An unchanged reload reuses prepared data. A first load of millions of records can still take a minute or longer. |
| LOOK / orbit feels slow | Keep Point Preview on. New objects preview 50,000 points; lower this if editor drawing is slow. Surface cards (Camera-Facing off) reuse geometry when the camera moves; SH colour updates after motion settles. Weight edits reuse geometry; colour edits still visit loaded splats in the background. Redshift convergence takes additional time. Maximum Splats reduces full model memory; Preview Points affects only drawing. |
| Out of memory | Close other GPU workloads, lower Gaussian Count for generation or Maximum Splats for import, and allow memory for both AI and C4D/Redshift. |
| Cancel does not interrupt immediately | Scan calculations check cancellation between blocks; C4D assembly yields between batches. A native allocation/commit already running must finish first. Final render/export has its own C4D/Redshift cancellation controls. |
| Estimated source camera unavailable | Keep `generation.json` next to its PLY. Older generations without camera metadata cannot use this feature. |

Installer logs are in `%LOCALAPPDATA%\ArgentumSplat\installer\logs`; the setup summary is `%LOCALAPPDATA%\ArgentumSplat\runtime\setup-result.json`. Other logs: per-job `generation.log`; runtime `setup.log` / `formats.log` for setup started from C4D; conversion `conversion.log` beside its cache. Report the relevant error text, input format and application versions. Logs/metadata can contain local paths; remove personal details and do not upload private source media.

## Plugin IDs

This preview deliberately preserves the development IDs used by existing local scenes:

| Registration | ID |
| --- | --- |
| Object | 1000007 |
| Toolbar command | 1000008 |
| Background-job message plugin | 1000009 |

They are **not guaranteed globally unique**. Another plugin using them can conflict even if it has a different name. Maxon provides [registered plugin identifiers](https://developers.maxon.net/forum/pid) for public distribution. Permanent IDs and an explicit migration path are pending; this release is marked as a preview for that reason. Do not choose random replacement IDs or silently change the object ID in scenes you need to reopen.

For evaluation, use a separate C4D preferences/plugin directory with no conflicting plugins. Keep backups of original scenes. This is a compatibility limitation, not a paid license or activation requirement.

## Uninstall

Close C4D and move `ArgentumSplat` out of its `plugins` directory. Generated models and the optional runtime remain in `%LOCALAPPDATA%\ArgentumSplat` so they are not lost with the plugin. Keep those files if you need your results; remove them manually only when you no longer need them.
