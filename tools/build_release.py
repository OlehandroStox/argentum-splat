"""Build a clean plugin distribution; exclude runtime, weights and local logs."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '0.6.2'


def main():
    output = ROOT / 'dist'
    output.mkdir(exist_ok=True)
    archive = output / f'ArgentumSplat-{VERSION}-C4D2027-Windows.zip'
    files = []
    for folder in ('ArgentumSplat', 'docs'):
        files.extend(p for p in (ROOT / folder).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts
                     and p.suffix not in ('.pyc', '.pyo', '.log'))
    files.extend(ROOT / name for name in ('README.md', 'README.ru.md', 'LICENSE', 'CHANGELOG.md'))
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(files):
            zf.write(path, path.relative_to(ROOT).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS.txt').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(f'{archive.name}: {len(files)} files, {archive.stat().st_size:,} bytes, SHA256 {digest}')


if __name__ == '__main__':
    main()
