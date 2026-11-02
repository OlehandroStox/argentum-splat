"""Build a clean plugin distribution; exclude runtime, weights and local logs."""
from pathlib import Path
import ast
import hashlib
import os
import re
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = ('README.md', 'README.ru.md', 'LICENSE', 'CHANGELOG.md')
# Release sources and authored documentation only. Runtime packages and models
# are installed separately, even if someone placed them inside the checkout.
SHIP_SUFFIXES = {'.py', '.pyp', '.ps1', '.cmd', '.md', '.txt', '.json',
                 '.png', '.gif', '.svg', '.h', '.res', '.str'}
PRIVATE_DIRECTORIES = {'__pycache__', 'venv', 'node_modules', 'runtime', 'models',
    'weights', 'checkpoints', 'wheel-cache', 'cache', 'caches', 'converted',
    'generated', 'logs', 'dist', 'build', 'tmp', 'temp', 'backups'}
PRIVATE_FILES = {'runtime.json', 'setup-result.json', 'credentials.json',
    'secrets.json', 'tokens.json', 'token.txt', 'config.local.json'}


def release_version(root):
    """Read literal package metadata without executing plugin startup code."""
    path = root / 'ArgentumSplat/argentum_splat/__init__.py'
    tree = ast.parse(path.read_text(encoding='utf8'), filename=str(path))
    values = [ast.literal_eval(node.value) for node in tree.body
              if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name)
                  and target.id == '__version__' for target in node.targets)]
    if len(values) != 1 or not isinstance(values[0], str) or not re.fullmatch(
            r'[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?', values[0]):
        raise ValueError('Package must declare one literal semantic __version__.')
    return values[0]


def numeric_wheel(root):
    """Read the declared optional binary without importing plugin startup code."""
    metadata = root / 'ArgentumSplat/argentum_splat/numeric_runtime.py'
    if not metadata.is_file():
        return None
    tree = ast.parse(metadata.read_text(encoding='utf8'))
    values = {node.targets[0].id: ast.literal_eval(node.value)
              for node in tree.body if isinstance(node, ast.Assign)
              and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id in {'WHEEL', 'SHA256'}}
    name, digest = values.get('WHEEL'), values.get('SHA256')
    if (not isinstance(name, str) or Path(name).name != name or
            '/' in name or '\\' in name or not name.endswith('.whl') or
            not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest)):
        raise ValueError('Invalid numeric wheel declaration.')
    return root / 'ArgentumSplat/vendor' / name, digest


def allowed_path(path, root, directory=False):
    relative = path.relative_to(root)
    if any(part.startswith('.') or part.casefold() in PRIVATE_DIRECTORIES for part in relative.parts):
        return False
    # Do not follow symlinks or Windows junctions into unrelated local data.
    attrs = getattr(path.lstat(), 'st_file_attributes', 0)
    if path.is_symlink() or attrs & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
        return False
    if not path.resolve().is_relative_to(root.resolve()):
        return False
    if directory:
        return True
    if (not path.is_file() or path.name.casefold() in PRIVATE_FILES or
            path.stem.casefold() in {'credentials', 'secrets', 'token', 'tokens', 'password', 'passwords'}):
        return False
    if path.suffix.casefold() == '.whl':
        declared = numeric_wheel(root)
        return declared is not None and path == declared[0]
    return path.suffix.casefold() in SHIP_SUFFIXES or path.name.casefold() == 'license'


def release_files(root):
    files = []
    declared = numeric_wheel(root)
    if declared is not None:
        wheel, digest = declared
        if (not wheel.is_file() or not allowed_path(wheel, root) or
                hashlib.sha256(wheel.read_bytes()).hexdigest() != digest):
            raise ValueError('Missing or corrupt declared numeric wheel.')
    for folder in ('ArgentumSplat', 'docs'):
        source = root / folder
        if not source.is_dir() or not allowed_path(source, root, directory=True):
            raise ValueError('Missing or linked release source directory: ' + folder)
        for parent, directories, names in os.walk(source, followlinks=False):
            parent = Path(parent)
            directories[:] = [name for name in directories
                if allowed_path(parent / name, root, directory=True)]
            files.extend(parent / name for name in names
                         if allowed_path(parent / name, root))
    for name in ROOT_FILES:
        path = root / name
        if not path.is_file() or not allowed_path(path, root):
            raise ValueError('Missing or linked release document: ' + name)
        files.append(path)
    return sorted(files)


def build_release(root=ROOT, output=None):
    root = Path(root).resolve()
    version = release_version(root)
    files = release_files(root)
    output = Path(output) if output is not None else root / 'dist'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'ArgentumSplat-{version}-C4D2027-Windows.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in files:
            zf.write(path, path.relative_to(root).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(f'{archive.name}: {len(files)} files, {archive.stat().st_size:,} bytes, SHA256 {digest}')
    return archive


def main():
    build_release()


if __name__ == '__main__':
    main()
