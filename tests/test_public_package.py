"""Plain Python checks for the public source and packaging; no Maya runtime."""
import ast
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
                self.assertEqual(len(zipped.namelist()), 8)
                self.assertIsNone(zipped.testzip())
                self.assertEqual(zipped.read('maya_max_target_camera/LICENSE'), (ROOT / 'LICENSE').read_bytes())
                self.assertFalse(any('__pycache__' in n or '/tests/' in n or '/.runtime/' in n for n in zipped.namelist()))
            self.assertIn(archive.name, checksum.read_text(encoding='utf-8'))

    def test_public_sources_have_no_workstation_paths(self):
        private_path = re.compile(r'[A-Za-z]:[\\/](?:Users|Documents and Settings)[\\/]')
        for folder in (SOURCE, ROOT / 'tests', ROOT / 'tools', ROOT / 'docs'):
            for file in folder.rglob('*'):
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

if __name__ == '__main__':
    unittest.main(verbosity=2)
