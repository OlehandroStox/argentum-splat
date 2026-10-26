# Rendering compatibility

Argentum Splat renders editable polygon cards in Redshift. Loading every source splat does not guarantee the same image as a dedicated Gaussian renderer.

The 0.8.2 material profile follows SuperSplat's deployed PlayCanvas 2.23.3 Gaussian falloff: normalized tails reach zero at sqrt(8) standard deviations, alpha below 1/255 is discarded, and the original opacity remains at the center. This corrects the previous longer tails and 0.99 alpha cap. Existing unmodified built-in shaders migrate when the plugin updates their material; hand-edited shaders are preserved. The embedded OSL uses a new kernel name to avoid reusing an older compiled program. See the [reference shader](https://github.com/playcanvas/engine/blob/b7655d8/src/scene/shader-lib/glsl/chunks/gsplat/frag/gsplat.js).

This profile change can alter the appearance of saved scenes. It aligns the opacity function with the reference; it does not establish pixel-identical rendering:

- Redshift composites linear-light material colors. SuperSplat can blend captured gamma-space colors; overlaps can therefore appear brighter in Redshift even with the same opacity.
- Redshift has a finite transparency trace depth, and close or coplanar cards can lose intersections. Dense scenes may show missing layers or bright patches. Increasing sampling does not fix missing intersections.
- Card depth order can differ from the viewer's radial sorting. Camera-facing cards are prepared for one view; secondary cameras, reflections and motion blur need separate evaluation.
- Website camera animation, tone mapping, background, bloom, sharpness and vignette are separate from the SOG data. Automatic framing estimates a usable starting view and does not recover those publishing settings.

Compare completed renders with a fixed camera and resolution. A successful import or automated test run proves neither visual parity nor smooth camera navigation. Report native viewport timing, rendered fixtures and unresolved differences separately when validating a release.

For scripted PNG/JPEG comparisons in an OCIO document, follow Maxon's `AllocateRenderBitmap` and `RENDERFLAGS_OCIO_BAKE_RENDERING` save workflow. Saving a raw render-space bitmap as an ordinary display image can make it look substantially darker; do not compensate for that export error by changing the splat colors. Preserve the scene's intended view transform.
