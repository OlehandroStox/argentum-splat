# Optional offline numeric runtime

This directory contains the unmodified NumPy 2.2.6 CPython 3.11 Windows x86-64
wheel published on [PyPI](https://pypi.org/project/numpy/2.2.6/#files):

`numpy-2.2.6-cp311-cp311-win_amd64.whl`

SHA-256: `e8213002e427c69c45a52bbd94163084025f533a55a59d6f9c5b820774ef3303`

The plugin first reuses an available NumPy. On a matching Windows Python 3.11
host, it can unpack this exact checksum-verified wheel into its own
`%LOCALAPPDATA%/ArgentumSplat/numeric/` cache. It does not run pip, download a
package, or install files into Cinema 4D's Python environment. Unsupported or
unavailable numeric runtimes retain the ordinary Python calculation path.

The release builder reads the filename and checksum literals from
`argentum_splat/numeric_runtime.py` without importing plugin code. It permits
only that exact artifact in this directory; unrelated wheels and binaries are
excluded. Corruption or a missing declared wheel prevents a release build.

## Third-party notice

NumPy and its bundled components retain their original copyrights and licenses,
independently of Argentum Splat's MIT license. The wheel's complete primary
license and component notices are reproduced without modification in
[LICENSE.numpy.txt](LICENSE.numpy.txt). All four original license members remain
intact inside the wheel:

- `numpy-2.2.6.dist-info/LICENSE.txt`
- `numpy/ma/LICENSE`
- `numpy/random/LICENSE.md`
- `numpy/_core/include/numpy/random/LICENSE.txt`

NumPy uses the BSD-3-Clause license. The primary notice also includes OpenBLAS,
LAPACK, bundled GCC runtime components and the complete GCC Runtime Library
Exception 3.1 and GPLv3 texts. Additional component notices include NCSA, MIT,
BSD and zlib terms. The wheel includes the Microsoft Visual C++ runtime DLL,
which retains Microsoft's terms and is not relicensed as BSD or MIT by this
project. See [Microsoft's redistribution documentation](https://learn.microsoft.com/cpp/windows/redistributing-visual-cpp-files).

Keep the wheel and its notices together and unmodified when redistributing this
plugin. This directory is the release's narrowly pinned binary exception;
populated developer runtimes, AI models and arbitrary downloaded packages are
not part of the plugin distribution.
