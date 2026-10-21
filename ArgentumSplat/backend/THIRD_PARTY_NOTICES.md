Argentum Splat uses the TripoSplat inference implementation by Tripo AI / VAST AI Research.

Source: https://github.com/VAST-AI-Research/TripoSplat
Pinned source revision: d8db9e018b413dd9c4a9fe22463781bf98e8e68d
The unmodified upstream Python files and MIT license are in vendor/.

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

Video input uses PyAV 16.0.1 (BSD-3-Clause), installed separately into the local
runtime from PyPI: https://pypi.org/project/av/16.0.1/ . PyAV's Windows wheel
includes FFmpeg libraries subject to their own terms. This source archive
does not redistribute the wheel or those binaries. Installed license notices
are retained in the runtime package. Source: https://github.com/PyAV-Org/PyAV .

TACTYC products were studied only through their public product descriptions.
This independently implemented plugin contains no TACTYC code, branding, or paid assets.
