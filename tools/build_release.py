#!/usr/bin/env python3
"""Build a clean, deterministic release ZIP without importing Maya."""
import argparse
import ast
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'maya_max_target_camera'
RUNTIME_FILES = (
    '使用说明.md', 'install_max_target_camera.py', 'reload_max_camera_menu.py',
    'load_menu_now.py', 'max_target_camera.py', 'max_target_camera_menu.py',
    'startup/userSetup.py',
)

def version():
    tree = ast.parse((SOURCE / 'max_target_camera.py').read_text(encoding='utf-8-sig'))
    return next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in node.targets))

def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ('maya_max_target_camera_v' + version() + '.zip')
    manifest = [(SOURCE / name, 'maya_max_target_camera/' + name) for name in RUNTIME_FILES]
    manifest.append((ROOT / 'LICENSE', 'maya_max_target_camera/LICENSE'))
    for source, _ in manifest:
        if source.suffix == '.py':
            ast.parse(source.read_text(encoding='utf-8-sig'), filename=source.name)
    with zipfile.ZipFile(archive, 'w') as zipped:
        for source, name in manifest:
            info = zipfile.ZipInfo(name, date_time=(2026, 11, 24, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zipped.writestr(info, source.read_bytes(), compresslevel=9)
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert sorted(zipped.namelist()) == sorted(name for _, name in manifest)
        for source, name in manifest:
            assert zipped.read(name) == source.read_bytes()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    checksum = output / 'SHA256SUMS.txt'
    checksum.write_text(digest + '  ' + archive.name + '\n', encoding='utf-8')
    return archive, checksum

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    archive, checksum = build(args.output_dir)
    print('Built:', archive)
    print(checksum.read_text(encoding='utf-8').strip())
