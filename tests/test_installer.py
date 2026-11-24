# -*- coding: utf-8 -*-
"""Installer filesystem checks; writes only to a temporary folder chosen by caller."""
from __future__ import absolute_import, division, print_function, unicode_literals
import io
import json
import os
import sys
import tempfile
import unittest

BASE = os.environ.get("MTC_SOURCE_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "maya_max_target_camera")))
sys.path.insert(0,BASE)
import install_max_target_camera as installer
OUT=os.environ.get('MTC_TEST_OUTPUT',os.path.join(os.path.dirname(BASE),'.test-results'))
if not os.path.isdir(OUT):
    os.makedirs(OUT)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.app=tempfile.mkdtemp(prefix='installer_test_',dir=OUT)

    def test_install_preserves_user_startup_and_env(self):
        os.makedirs(os.path.join(self.app,'scripts'))
        files=[os.path.join(self.app,'scripts','userSetup.py'),os.path.join(self.app,'Maya.env')]
        for path in files:
            with io.open(path,'w',encoding='utf-8') as f:
                f.write('untouched user settings\n')
        result=installer.install_files(self.app,BASE)
        self.assertEqual(len(result['installed_files']),3)
        for path in files:
            self.assertEqual(installer._read(path),'untouched user settings\n')
        self.assertIn('PYTHONPATH +:= scripts',installer._read(result['module_file']))
        self.assertFalse(result['modified_user_setup'])
        self.assertTrue(os.path.isfile(os.path.join(result['scripts_dir'],'userSetup.py')))

    def test_reinstall_backs_up_managed_files(self):
        first=installer.install_files(self.app,BASE)
        second=installer.install_files(self.app,BASE)
        self.assertEqual(len(second['backups']),3)
        self.assertTrue(all(os.path.isfile(p) for p in second['backups']))
        self.assertEqual(first['module_file'],second['module_file'])

    def test_refuses_unowned_module_file(self):
        os.makedirs(os.path.join(self.app,'modules'))
        path=os.path.join(self.app,'modules','MaxTargetCamera.mod')
        with io.open(path,'w',encoding='utf-8') as f:
            f.write('another user module\n')
        with self.assertRaises(RuntimeError):
            installer.install_files(self.app,BASE)
        self.assertEqual(installer._read(path),'another user module\n')

    def test_refuses_unowned_module_directory(self):
        os.makedirs(os.path.join(self.app,'modules','MaxTargetCamera'))
        with self.assertRaises(RuntimeError):
            installer.install_files(self.app,BASE)

    def test_disable_keeps_installed_sources_and_is_repeatable(self):
        receipt=installer.install_files(self.app,BASE)
        result=installer.disable_files(self.app)
        self.assertFalse(os.path.exists(receipt['module_file']))
        self.assertTrue(os.path.isfile(result['module_backup']))
        self.assertTrue(all(os.path.isfile(p) for p in receipt['installed_files']))
        self.assertTrue(installer.disable_files(self.app)['already_disabled'])
        self.assertTrue(installer.install_files(self.app,BASE)['module_file'])


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(InstallerTests))
    report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'successful':result.wasSuccessful()}
    with io.open(os.path.join(OUT,'installer_test_report.json'),'w',encoding='utf-8') as f:
        f.write(json.dumps(report,indent=2))
    sys.exit(0 if result.wasSuccessful() else 1)
