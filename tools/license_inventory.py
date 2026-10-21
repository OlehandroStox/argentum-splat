"""Record installed dependency metadata and notice hashes; not a legal verdict.

Run with the private runtime's Python. No imports of third-party packages,
network calls, personal paths, or credentials are included in the report.
"""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform


def notice(path, relative):
    return {"file": str(relative).replace("\\", "/"),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def is_notice(path):
    name = path.name.lower()
    return any(word in name for word in ("license", "licence", "notice", "copying"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--npm-root", type=Path)
    args = parser.parse_args()
    packages = []
    for dist in sorted(metadata.distributions(), key=lambda d: d.metadata['Name'].lower()):
        meta = dist.metadata
        label = meta.get('License-Expression') or meta.get('License') or ''
        # Some packages embed their entire license in the metadata field.
        if len(label) > 160:
            label = 'See bundled license text and classifiers'
        files = []
        seen = set()
        for relative in dist.files or []:
            path = Path(dist.locate_file(relative))
            key = str(path.resolve()).lower()
            if is_notice(path) and path.is_file() and key not in seen:
                seen.add(key)
                files.append(notice(path, relative))
        packages.append({'name': meta['Name'], 'version': dist.version,
                         'declared_license': label,
                         'license_classifiers': [x for x in meta.get_all('Classifier', []) if x.startswith('License ::')],
                         'sources': meta.get_all('Project-URL', []) + ([meta['Home-page']] if meta.get('Home-page') else []),
                         'requires_dist': meta.get_all('Requires-Dist', []),
                         'notices': files})
    npm = []
    if args.npm_root:
        for manifest in sorted(args.npm_root.rglob('package.json')):
            data = json.loads(manifest.read_text(encoding='utf-8'))
            if not data.get('name') or not data.get('version'):
                continue
            root = manifest.parent
            npm.append({'name': data['name'], 'version': data['version'],
                        'declared_license': data.get('license'),
                        'source': data.get('repository'),
                        'notices': [notice(p, p.relative_to(root)) for p in sorted(root.rglob('*'))
                                    if p.is_file() and is_notice(p) and 'node_modules' not in p.relative_to(root).parts]})
    report = {'scope': 'Installed metadata snapshot, not a complete native-library SBOM or license approval. Bundled native components retain separate terms.',
              'python': platform.python_version(), 'python_packages': packages, 'npm_packages': npm}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Recorded {len(packages)} Python distributions and {len(npm)} npm package manifests.')


if __name__ == '__main__':
    main()
