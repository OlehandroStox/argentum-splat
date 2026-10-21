# License review — 21 October 2026

The distributable integration may be shared freely and supported by optional
donations under the inspected licenses, subject to their conditions. This is a
conditional engineering conclusion, not a legal clearance of all upstream IP.
Read [scope, conditions and exclusions](../../ArgentumSplat/LICENSE_SCOPE.md).

## Examined

- Bundled Python sources, adapted SPZ decoding, camera-token implementation,
  upstream MIT notices, example-media credits and installer download sources.
- Five checkpoint roles and pinned model/source revisions; license texts
  checked against the pinned upstream revisions in `backend/licenses/sources.json`.
- All 27 installed Python distributions in each of two environments:
  [Python 3.10](runtime-python310.json) and [Python 3.12](runtime-python312.json).
  The latter also records all eight npm dependency package manifests and
  license-file hashes. Reports omit personal absolute filesystem paths.
- Python/Node distribution license bundles, PyTorch LICENSE/NOTICE, NumPy's
  compound license and FFmpeg's runtime-reported license. This does not constitute
  a complete independently verified SBOM of every embedded native library.

## Findings and corrections

1. Preserved the additional VAST/Microsoft MIT notice for the source-camera
   reference from TripoSplat-Training; attribution now links to that notice.
2. Added tqdm 4.67.1's upstream MIT/MPL notice. Its examined installed wheel had
   no standalone license file. The wheel itself is not redistributed here.
3. Corrected the converter's oversimplified licensing description:
   @adobe/spz 0.2.3 declares ISC in metadata but ships a Niantic MIT LICENSE;
   webgpu 0.6.2 declares MIT but ships a Dawn/Tint BSD-3-Clause LICENSE.md.
   Preserved copies of the actual texts instead of relying only on metadata.
4. Explicitly separated the integration's MIT grant from DINOv3, NVIDIA,
   FFmpeg, runtime distributions and other third-party terms. Added notices
   before installer downloads without inventing a new license acceptance screen.
5. Documented optional support without promising a tax exemption or a payment
   service's ability to pay out. No dependency is relicensed by a donation.

## Native-library caveat

The PyAV 16.0.1 Windows wheel's seven FFmpeg libraries report
`LGPL version 3 or later`. The build configuration also includes x264/x265 flags.
Runtime self-reporting does not establish the license compliance of every codec
or a complete corresponding-source chain. Therefore this review does **not**
approve repackaging that runtime. The plugin ZIP contains no such binaries;
setup obtains the upstream wheel from PyPI. See
[FFmpeg's guidance](https://ffmpeg.org/legal.html) and
[PyAV's source](https://github.com/PyAV-Org/PyAV/tree/v16.0.1).

## Reproduce / maintain

Run `tools/license_inventory.py` with the installed AI Python, supplying
`--output report.json` and optionally `--npm-root path/to/node_modules`.
The resulting JSON is evidence, not a license decision. Inspect full notices
when a package changes. Direct AI dependencies are version-pinned, but their
transitive dependencies and pip are not fully locked; these two snapshots are
not an assurance about packages resolved in future installations.

Public example media is credited under the upstream repository's MIT notice.
That notice is evidence of the published grant, not independent proof of the
provenance of the image, training data or generated output. The review did not
compare this source against proprietary third-party implementations.
