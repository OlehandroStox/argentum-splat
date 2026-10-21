# Demonstration media and credits

The house input is the public **`static/example_inputs/building_stone_house.webp`** example from [TripoSplat / VAST AI Research](https://github.com/VAST-AI-Research/TripoSplat/blob/d8db9e018b413dd9c4a9fe22463781bf98e8e68d/static/example_inputs/building_stone_house.webp), converted to PNG. The upstream repository includes an [MIT license](TripoSplat-LICENSE.txt), reproduced here. The underlying example is not presented as original artwork by ARGENTUM.

The model was generated locally with TripoSplat through Argentum Splat:

- 65,536 Gaussians, 20 steps, seed 42.
- About 44.843 seconds of AI processing on an RTX 4070 12 GB in that run.
- Hidden sides are inferred from a single image, not captured from multiple photographs.

`redshift-front.png` and `redshift-rear.png` are actual Cinema 4D / Redshift renders of that model using the plugin. `house-orbit.gif` contains 36 real views of the exported PLY, rendered by a separate orthographic Gaussian alpha compositor using the covariance and opacity values. It is not a screen recording, an AI-generated animation, or proof of Redshift viewport frame rate. Its timing is presentation timing, not generation speed. `house-orbit.png` is its first frame.

The reference compositor uses a dark background, 3-sigma support, a 0.25-pixel covariance floor and alpha capped at 0.99. Native Gaussian compositing and Redshift card shading are different; colour transforms and layering can also differ.

The icon is original Argentum Splat artwork, distributed with this project's MIT integration license. No private source photographs or paid assets are included.
