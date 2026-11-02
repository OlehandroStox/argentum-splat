Argentum Splat uses the TripoSplat inference implementation by Tripo AI / VAST AI Research.

Source: https://github.com/VAST-AI-Research/TripoSplat
Pinned source revision: d8db9e018b413dd9c4a9fe22463781bf98e8e68d
The upstream Python implementation and MIT license are in vendor/. The bundled
README and a callback docstring are adapted for this integration; runtime behavior
and license notices are unchanged.

Public model repository: https://huggingface.co/VAST-AI/TripoSplat
Pinned model revision: 56a96e603204ec410c4da60c13ea4fa09a2169a9
The upstream README and model card label TripoSplat code and model weights MIT.
This is not a blanket MIT grant over the complete inference environment.
Model weights are downloaded separately by setup_backend.ps1 and are not included in this plugin package.
The installer verifies each downloaded checkpoint against the SHA-256 published by Hugging Face.

Component-specific upstream terms:

| Component | Upstream terms | Primary source |
| --- | --- | --- |
| TripoSplat flow model and Gaussian decoder | MIT | https://github.com/VAST-AI-Research/TripoSplat |
| DINOv3 image encoder | DINOv3 License (custom Meta license; not MIT) | https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md |
| FLUX.2 autoencoder | Apache License 2.0 | https://github.com/black-forest-labs/flux2#flux2-autoencoder |
| BiRefNet background removal | MIT | https://github.com/ZhengPeng7/BiRefNet/blob/main/LICENSE |

Built with DINOv3. DINOv3 is a Meta model. Its separate license governs applicable
DINO materials and derivatives, including redistribution and use conditions.
The VAST model repository supplies the converted auxiliary checkpoints; it does
not document a separate, component-by-component chain of license grants.
Its top-level MIT label is therefore not treated here as replacing upstream terms.
The FLUX.2 autoencoder is separately released under Apache 2.0; this pipeline does
not download or execute the non-commercial FLUX.2-dev image-generation model.
Unmodified copies of the component license texts and pinned source URLs are in
licenses/. These notices do not relicense upstream materials.

Dependencies include PyTorch, Torchvision, NumPy, Pillow, safetensors, tqdm, and huggingface_hub;
their respective licenses are installed with their Python packages.

## Photos reconstruction

Set Up Photos downloads Brush 0.3.0 from its official release and checks the pinned SHA-256. Its original LICENSE, README and CHANGELOG remain beside the executable. Brush uses Apache-2.0: https://github.com/ArthurBrussee/brush/tree/v0.3.0 .
PyCOLMAP 4.2.1 is installed with its wheel's license bundle: https://pypi.org/project/pycolmap/4.2.1/ . COLMAP uses BSD-3-Clause; third-party components retain their own notices. NumPy 2.2.6 and Pillow 11.3.0 retain their package licenses. These Photos binaries are not included in the plugin ZIP.

## Private Python bootstrap

When a compatible working AI environment is absent, setup downloads
**CPython 3.12.15**, Windows x86-64, from Astral's **python-build-standalone**
release **20261020**. The archive is checked against the SHA-256 pinned in
`setup_python.ps1` before extraction. The downloaded Python binary is not
included in this plugin's source or release ZIP.

This is an Astral-built CPython distribution, not a Windows binary supplied
by the Python Software Foundation. CPython and the distribution's bundled
components retain their respective licenses. Setup retains the license files
shipped in the runtime; the plugin's MIT license does not replace them.

- Build project and source: https://github.com/astral-sh/python-build-standalone
- Pinned release: https://github.com/astral-sh/python-build-standalone/releases/tag/20261020
- Build-project license: https://github.com/astral-sh/python-build-standalone/blob/20261020/LICENSE
- CPython source and license: https://github.com/python/cpython/tree/v3.12.15

The private installation does not modify system PATH or Cinema 4D's Python.
Existing compatible AI environments may continue using their original Python
distribution and its associated licenses instead.

## Additional attribution and runtime license audit (0.5.1)

The reference-camera token interpretation in `source_camera.py` follows
TripoSplat-Training (VAST / Microsoft). Its MIT notice is preserved in
`licenses/TripoSplat-Training-LICENSE.txt`. This does not imply that the full
training pipeline or its dependencies are included in Argentum Splat.

`tqdm` 4.67.1 uses MIT for its original contributions and MPL-2.0 for other
contributions; the upstream notice is now included in `licenses/tqdm-LICENCE.txt`.
The inspected wheel did not contain a standalone license file. We do not modify
or redistribute that wheel. MPL-covered source remains available upstream.

PyTorch's BSD-3-Clause label does not cover every bundled component. Its wheel
contains a long LICENSE and NOTICE, including NVIDIA component terms. NumPy,
Pillow, CPython, Node.js, pip and setuptools also contain third-party components.
Keep their complete license bundles; do not replace them with this project's MIT
license.

See `../LICENSE_SCOPE.md` for distribution boundaries, model-use restrictions
and voluntary support. The release's `docs/licenses/` directory records installed
Python and npm package metadata and notice hashes, including transitive packages.
These are environment snapshots, not a future-version or native-library audit.
