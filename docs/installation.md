# Installation & troubleshooting

[README](../README.md) · [Русская быстрая установка](../README.ru.md#быстрая-установка)

## Install the plugin

Download the named Windows ZIP asset from [Releases](https://github.com/OlehandroStox/argentum-splat/releases), extract it, and close Cinema 4D. Run `ArgentumSplat/Install.cmd` from the extracted folder. Do not run it inside the ZIP viewer.

For a manual install, open C4D Preferences → **Open Preferences Folder**, close C4D and copy the whole `ArgentumSplat` directory into its `plugins` directory (create `plugins` if needed). The result should be:

```text
<Cinema 4D 2027 preferences>/plugins/
└── ArgentumSplat/
    ├── ArgentumSplat.pyp
    ├── argentum_splat/
    ├── backend/
    └── res/
```

Restart C4D and choose **Extensions → ArgentumSplat → Argentum Splat**. If the installer finds multiple 2027 preferences directories, use manual installation or pass `-PreferencesFolder` to `install.ps1`. Install only one copy in C4D's plugin search paths.

The installer backs up an existing plugin folder in `ArgentumSplat-backups` beside `plugins`. It does not change your startup layout. To add a toolbar icon, drag **Argentum Splat - Image to 3D** from **Customize Commands** to a palette and save your layout. The command is hidden from Extensions to avoid a duplicate menu entry.

## Optional local AI

Install official Python 3.10, 3.11 or 3.12 with the Windows `py` launcher. Use an NVIDIA Ampere-or-newer GPU with BF16 CUDA support and an appropriate current NVIDIA driver. The tested setup is Windows / C4D 2027.0.0 / RTX 4070 12 GB; requirements vary with scene and model size.

Click **Set Up AI / Extra Formats** and wait for Status to finish. The installer uses a separate environment at `%LOCALAPPDATA%\ArgentumSplat\runtime`; it does **not** install packages into C4D's Python. Initial downloads include PyTorch CUDA wheels and multiple model checkpoints. Keep several GB available for downloads, environment and weights; this is not a small plugin-only download.

If Python is not found, run from the plugin directory in PowerShell, substituting your real Python path:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_backend.ps1 -PythonExe "C:\path\to\python.exe"
```

This sets execution policy for that process only. Review the script before running downloaded code. The supported AI setup is Windows x64 / NVIDIA; CPU-only, AMD and macOS inference are not supported here.

## Optional extra formats

Bundled SOG, KSPLAT, SPZ v4 and packed PlayCanvas PLY use the separately installed PlayCanvas converter. The combined setup button installs it; alternatively run `setup_formats.ps1` from PowerShell. It uses Node 22+ if suitable or downloads the pinned official portable Node runtime. Files are converted locally; originals remain unchanged and the output is cached under `%LOCALAPPDATA%\ArgentumSplat\converted`.

Native Gaussian PLY, SPLAT and SPZ v2/v3 work without AI weights or the converter. Video/frame extraction needs the separate Python runtime with PyAV.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No Extensions entry | Restart C4D; check folder nesting and duplicate installs. Read C4D Console and `startup_error.log` if created beside the `.pyp`. A development-ID collision can prevent registration. |
| Black RS Render View | Confirm IPR is started, the render camera sees the model, and the object/material loaded successfully. Apply Source Fidelity for self-lit source colour. If data is loaded but layers disappear, inspect transparency depth or use Set Redshift Detail Quality. |
| Points in the viewport | Point Preview is enabled. It does not reduce Redshift output. Disable it to see cards in the editor. |
| SH sliders disabled | The file has no SH1–SH3 coefficients. Single-image TripoSplat results are SH0. |
| Video/sequence fails | Preview the selected frame. Frame index starts at 0; sequences use a filename offset. Missing frames, unsupported codecs and corrupt media report errors in Status. |
| LOOK feels slow | Weight edits reuse geometry; colour edits still traverse all loaded splats. Redshift convergence takes additional time. Reduce Maximum Splats and reload for a lighter model. Preview Points only limits point drawing. |
| Out of memory | Close other GPU workloads, lower Gaussian Count for generation or Maximum Splats for import, and allow memory for both AI and C4D/Redshift. |
| Cancel does not interrupt immediately | It stops background tasks. Synchronous C4D geometry evaluation can temporarily occupy the main thread. |
| Estimated source camera unavailable | Keep `generation.json` next to its PLY. Older generations without camera metadata cannot use this feature. |

Logs: per-job `generation.log`; runtime `setup.log` / `formats.log`; conversion `conversion.log` beside its cache. Report the relevant error text, input format and application versions. Logs/metadata can contain local paths; remove personal details and do not upload private source media.

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
