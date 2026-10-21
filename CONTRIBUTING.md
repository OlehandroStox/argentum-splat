# Contributing

Bug reports, documentation improvements and focused fixes are welcome.

1. Open an issue describing the problem or proposed change.
2. Include plugin, Cinema 4D and Redshift versions, operating system, GPU, input format, steps to reproduce, and the relevant Status message.
3. Use a small shareable example. Remove personal paths, private images and credentials from logs.
4. For code changes, run `python -m unittest discover -s tests -v` with `requirements-test.txt` installed. Describe any native C4D checks separately.

Keep the pure Python parser/geometry code independent of `c4d` so it remains testable. Do not add model weights, virtual environments, caches, credentials or large generated scenes. Preserve third-party notices and pinned source provenance.

Development plugin IDs are retained in this preview. Do not change them without an agreed registration and migration plan: saved C4D scenes identify objects by their plugin ID.

Contributions are submitted under the integration's MIT license; upstream components retain their own terms. The project does not promise response times or support SLAs.
