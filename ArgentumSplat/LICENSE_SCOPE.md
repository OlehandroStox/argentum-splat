# License scope and voluntary support

Reviewed 21 October 2026 for the Windows source/plugin distribution.

## What you may distribute

The independently written Argentum Splat integration is MIT licensed. You may
share it for free, modify it, sell copies and accept voluntary support, while
retaining the copyright and permission notices. Bundled third-party source is
subject to its preserved notices; it is not owned exclusively by ARGENTUM.
No inspected license prohibits voluntary donations for this integration.

The release ZIP includes the plugin, installer scripts, documentation, demo
media and license texts. Its one bundled binary exception is the unchanged,
SHA-256-pinned NumPy 2.2.6 CPython 3.11 Windows x86-64 wheel, including its
upstream native libraries and original notices. This exception was added on
26 October 2026; see [the numeric runtime notice](vendor/README.md) and its
[complete primary license bundle](vendor/LICENSE.numpy.txt). These components
retain their own licenses independently of Argentum Splat's MIT license.

The ZIP does **not** include other wheels, AI checkpoints, Python/Node
executables, node_modules, CUDA, Brush, Cinema 4D or Redshift binaries.
Installers download other optional dependencies from their upstream hosts.
Those dependencies retain their own licenses; the plugin's MIT license does
not replace their terms.

Do not distribute a copy of your populated AppData runtime as though it were the
MIT plugin. Redistributing those binaries or models needs a separate review of
notices, source availability, license copies and vendor redistribution terms.

## AI models

| Component | Applicable published terms |
| --- | --- |
| TripoSplat inference source, flow model and decoder | MIT, VAST |
| DINOv3 encoder | Custom Meta DINOv3 License; **not MIT** |
| FLUX.2 autoencoder | Apache-2.0; not the FLUX.2-dev generation model |
| BiRefNet background removal | MIT |

Built with DINOv3. Read [DINOv3's license](backend/licenses/DINOv3-LICENSE.md)
before downloading/using its materials. It grants use and redistribution rights
subject to its terms, including trade-control and prohibited-use restrictions;
it is not an unrestricted open-source grant. Using or distributing the materials
constitutes acceptance under its text. A donation does not override those terms.
The installer neither signs agreements nor asserts eligibility on your behalf.

Weights are fetched from the pinned VAST-AI/TripoSplat repository. Its MIT model
card cannot supersede the separate auxiliary-model licenses. We have not
independently established the full provenance/authorization chain for converted
weights or the model's training data. No universal rights warranty for generated
assets is made. Use inputs you have permission to process and publish.

## Other dependencies and notices

See [AI/runtime notices](backend/THIRD_PARTY_NOTICES.md) and
[format-converter notices](backend/formats/THIRD_PARTY_NOTICES.txt).
They cover MIT, BSD, Apache, MPL, PSF, LGPL and vendor-specific components.
Retain upstream license bundles. Attribution is a license condition, not an
endorsement or advertising arrangement.

Cinema 4D and Redshift must be obtained and used under Maxon's own licenses.
This plugin does not grant or supply those licenses. Temporary Plugin IDs remain
a separate compatibility/release issue; this review does not resolve it.

## Voluntary support

[Support the author on Boosty](https://boosty.to/olehandrostox/donate).
Support is optional: no payment is required to download or use this release.
It does not buy extra IP rights, exclusivity, priority service or a warranty.

Software-license permission to accept support is separate from payment-service
eligibility, withdrawal verification, sanctions and tax obligations. Calling a
payment a donation does not by itself establish a tax exemption in Russia or
elsewhere. This review does not certify Boosty payment/withdrawal availability
or the author's individual tax status. Consult the service's current terms and
a qualified adviser for those questions.

## Limits of the review

This is an engineering review of available license texts and installed package
metadata, not a legal opinion or proof of every upstream author's ownership.
Runtime snapshots and findings are in the release's `docs/licenses/` directory.
Python transitive dependencies can change on a new installation; re-audit after
dependency changes. Native libraries bundled upstream need their full notices,
not just their parent package's metadata label.
