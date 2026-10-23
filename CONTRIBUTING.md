# Contributing

Focused fixes, documentation improvements and reproducible bug reports are welcome.

- Find the plugin version at the bottom of **Help**. Include it, Cinema 4D/Redshift versions, input format, reproduction steps and the relevant Status message in an issue.
- Remove personal paths, credentials and private media from anything you share. Use a small example you have permission to publish.
- For code changes, install `requirements-test.txt` and run `python -m unittest discover -s tests -v`. Keep parser/geometry code independent of `c4d` where possible.
- Do not commit model weights, environments, caches or generated scenes. Preserve third-party notices and source provenance.
- Coordinate Plugin ID changes with a saved-scene migration plan; see [compatibility](docs/installation.md#plugin-ids).

Contributions use the project's MIT license; upstream components retain their own terms.
