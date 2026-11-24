"""Plain Python checks for the public source and packaging; no Maya runtime."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'maya_max_target_camera'

class PublicPackageTests(unittest.TestCase):
    def test_runtime_sources_parse(self):
        files = list(SOURCE.rglob('*.py'))
        self.assertEqual(len(files), 6)
        for file in files:
            ast.parse(file.read_text(encoding='utf-8-sig'), filename=file.name)

    def test_clean_zip_has_exactly_eight_files_and_license(self):
        spec = importlib.util.spec_from_file_location('release_builder', ROOT / 'tools/build_release.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as tmp:
            archive, checksum = builder.build(tmp)
            with zipfile.ZipFile(archive) as zipped:
                expected = {
                    'maya_max_target_camera/' + name for name in (
                        '使用说明.md', 'install_max_target_camera.py',
                        'reload_max_camera_menu.py', 'load_menu_now.py',
                        'max_target_camera.py', 'max_target_camera_menu.py',
                        'startup/userSetup.py', 'LICENSE')
                }
                self.assertEqual(set(zipped.namelist()), expected)
                self.assertEqual(len(zipped.namelist()), len(expected))
                self.assertIsNone(zipped.testzip())
                self.assertEqual(zipped.read('maya_max_target_camera/LICENSE'), (ROOT / 'LICENSE').read_bytes())
                self.assertFalse(any('__pycache__' in n or '/tests/' in n or '/.runtime/' in n for n in zipped.namelist()))
            self.assertIn(archive.name, checksum.read_text(encoding='utf-8'))

    def test_public_sources_have_no_workstation_paths(self):
        private_path = re.compile(r'[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]')
        files = [ROOT / name for name in ('README.md', 'README.en.md', 'CHANGELOG.md')]
        for folder in (SOURCE, ROOT / 'tests', ROOT / 'tools', ROOT / 'docs'):
            files.extend(folder.rglob('*'))
        for file in files:
            if file.suffix not in ('.py', '.md', '.yml'): continue
            self.assertIsNone(private_path.search(file.read_text(encoding='utf-8-sig')), str(file.relative_to(ROOT)))

    def test_public_images_have_no_embedded_text_metadata(self):
        for name in ('target-first-guide.png', 'install-guide.png', 'maya-viewport-example.png', 'display-controls-v1.5.png'):
            payload = (ROOT / 'docs/images' / name).read_bytes()
            self.assertEqual(payload[:8], b'\x89PNG\r\n\x1a\n')
            offset = 8
            while offset < len(payload):
                size = int.from_bytes(payload[offset:offset+4], 'big')
                kind = payload[offset+4:offset+8]
                self.assertNotIn(kind, (b'tEXt', b'iTXt', b'zTXt', b'eXIf'))
                offset += size + 12
                if kind == b'IEND': break

    def test_release_versions_and_download_links_match(self):
        def declared_version(path):
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            return next(ast.literal_eval(node.value) for node in tree.body
                        if isinstance(node, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in node.targets))
        version = declared_version(SOURCE / 'max_target_camera.py')
        self.assertEqual(version, declared_version(SOURCE / 'install_max_target_camera.py'))
        self.assertIn('版本：' + version, (SOURCE / '使用说明.md').read_text(encoding='utf-8-sig'))
        self.assertIn('## ' + version + ' — ', (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8-sig'))
        link = '/releases/download/v{0}/maya_max_target_camera_v{0}.zip'.format(version)
        for name in ('README.md', 'README.en.md'):
            self.assertIn(link, (ROOT / name).read_text(encoding='utf-8-sig'))

    def test_camera_transform_scale_stays_locked(self):
        tree = ast.parse((SOURCE / 'max_target_camera.py').read_text(encoding='utf-8-sig'))
        create = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'create_camera')
        axes = [n for n in ast.walk(create) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'scale' for t in n.targets)]
        self.assertEqual([ast.literal_eval(n.value) for n in axes], [('sx', 'sy', 'sz')])
        calls = [n for n in ast.walk(create) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == '_lock']
        self.assertTrue(any([a.id if isinstance(a, ast.Name) else None for a in n.args]
                            == ['camera', 'scale'] for n in calls))

    def test_no_experimental_native_r_adapter_in_runtime(self):
        self.assertFalse((SOURCE / 'max_target_camera_manip.py').exists())
        markers = ('max_target_camera_manip', 'native_scale_spec',
                   'install_native_scale_tool', 'maxTargetCameraDisplayScale',
                   'MPxManipContainer', 'MFnScaleManip')
        for file in SOURCE.rglob('*.py'):
            text = file.read_text(encoding='utf-8-sig')
            for marker in markers:
                self.assertNotIn(marker, text, str(file.relative_to(ROOT)))

    def test_release_build_is_deterministic_and_checksums_match(self):
        spec = importlib.util.spec_from_file_location('deterministic_builder', ROOT / 'tools/build_release.py')
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        with tempfile.TemporaryDirectory() as tmp:
            first, first_sum = builder.build(Path(tmp) / 'first')
            second, second_sum = builder.build(Path(tmp) / 'second')
            self.assertEqual(first.read_bytes(), second.read_bytes())
            expected = hashlib.sha256(first.read_bytes()).hexdigest() + '  ' + first.name + '\n'
            self.assertEqual(first_sum.read_text(encoding='utf-8'), expected)
            self.assertEqual(second_sum.read_text(encoding='utf-8'), expected)

if __name__ == '__main__':
    unittest.main(verbosity=2)
