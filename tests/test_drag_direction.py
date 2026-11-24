# -*- coding: utf-8 -*-
"""Pure-Python regression for target-first mouse placement. No Maya session needed."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('MTC_SOURCE_DIR', str(ROOT / 'maya_max_target_camera')))
OUT = Path(os.environ.get('MTC_TEST_OUTPUT', str(ROOT / '.test-results')))

class FakeCmds:
    def __init__(self):
        self.button = 1
        self.anchor = (-0.2, 0.3, 9.0)
        self.pointer = (0.7, -0.1, 9.0)
        self.nodes = {}
        self.selection = ['existing_user_object']
        self.creates = []
        self.moves = []
        self.warnings = []
        self.attrs = {}
        self.context = 'MaxTargetCameraDrawContext'
    def draggerContext(self, context, **kw):
        if kw.get('button'): return self.button
        if kw.get('anchorPoint'): return self.anchor
        if kw.get('dragPoint'): return self.pointer
        if 'drawString' in kw: self.draw_string = kw['drawString']
    def getPanel(self, **kw):
        return ['modelPanel4'] if kw.get('type') else 'modelPanel4'
    def ls(self, **kw): return list(self.selection)
    def xform(self, node, **kw):
        self.moves.append(node)
        self.nodes[node] = tuple(kw['translation'])
    def setAttr(self, plug, value): self.attrs[plug] = value
    def refresh(self, **kw): pass
    def warning(self, text): self.warnings.append(text)
    def window(self, *a, **kw): return False
    def select(self, nodes=None, **kw):
        self.selection = [] if kw.get('clear') else (list(nodes) if isinstance(nodes, (list,tuple)) else [nodes])
    def objExists(self, node): return node == 'existing_user_object' or node in self.nodes
    def currentCtx(self): return self.context
    def setToolTo(self, context): self.context = context
    def create(self, **kw):
        self.creates.append(kw)
        self.nodes.update({'rig':None, 'cam':tuple(kw['camera_position']), 'target':tuple(kw['target_position'])})
        return {'root':'rig', 'camera':'cam', 'target':'target', 'shape':'shape'}
    def delete(self, root):
        assert root == 'rig'
        self.nodes.clear()

fake_maya = types.ModuleType('maya')
fake_maya.cmds = types.ModuleType('maya.cmds')
fake_maya.utils = types.ModuleType('maya.utils')
spec = importlib.util.spec_from_file_location('mtc_target_first_test', str(SOURCE/'max_target_camera.py'))
tool = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'maya':fake_maya,'maya.cmds':fake_maya.cmds,'maya.utils':fake_maya.utils}):
    spec.loader.exec_module(tool)

class TargetFirstTests(unittest.TestCase):
    def setUp(self):
        self.c = FakeCmds()
        self.deferred = []
        fake_maya.utils.executeDeferred = self.deferred.append
        self.layout = {'eye':(0.,0.,10.),'forward':(0.,0.,-1.),'center':(0.,0.,0.),
                       'depth':10.,'orthographic':False,'half_width':10.,'half_height':10.,'lens':35.}
        self.patches = [patch.object(tool,'cmds',self.c),
                        patch.object(tool,'create_camera',self.c.create),
                        patch.object(tool,'delete_rig',self.c.delete),
                        patch.object(tool,'_view_layout',lambda panel:self.layout),
                        patch.dict(sys.modules, {'maya':fake_maya,'maya.cmds':fake_maya.cmds,'maya.utils':fake_maya.utils})]
        for p in self.patches:p.start()
        for p in self.patches:self.addCleanup(p.stop)
        self.d = tool._DrawCamera('Regression')
    def draw(self):self.d.press();self.d.drag()
    def test_press_is_fixed_target_on_first_drag(self):
        self.draw()
        self.assertEqual(self.c.nodes['target'],(-2.,3.,0.))
        self.assertEqual(self.c.nodes['cam'],(7.,-1.,0.))
        self.assertTrue(self.c.creates[0]['keep_horizon'])
    def test_repeated_drags_move_only_camera(self):
        self.draw()
        for p in ((0.9,0.1,9.),(-0.6,0.2,9.),(0.2,-0.3,9.)):
            self.c.pointer=p;self.d.drag()
            self.assertEqual(self.c.nodes['target'],(-2.,3.,0.))
            self.assertEqual(self.c.nodes['cam'],tool._draw_world_point(self.layout,p))
        self.assertEqual(self.c.moves,['cam']*3)
        self.assertEqual(len(self.c.creates),1)
    def test_release_selects_camera_and_restores_move_tool(self):
        self.draw();self.d.release()
        self.assertEqual(self.c.selection,['cam'])
        self.assertTrue(self.d.finished)
        for fn in self.deferred:fn()
        self.assertEqual(self.c.context,'moveSuperContext')
    def test_finalizing_finished_gesture_keeps_rig(self):
        self.draw();self.d.release();self.d.cancel()
        self.assertIn('rig',self.c.nodes)
    def test_cancel_removes_preview_and_restores_selection(self):
        self.draw();self.d.cancel()
        self.assertFalse(self.c.nodes)
        self.assertEqual(self.c.selection,['existing_user_object'])
    def test_click_without_drag_does_not_create_camera(self):
        self.d.press();self.d.release()
        self.assertFalse(self.c.creates)
    def test_zero_distance_drag_does_not_create_camera(self):
        self.c.pointer=self.c.anchor;self.draw()
        self.assertFalse(self.c.creates)
    def test_non_left_press_never_creates_camera(self):
        for button in (2,3):
            self.c.button=button;self.draw();self.d.release()
        self.assertFalse(self.c.creates)
    def test_orthographic_also_anchors_target(self):
        self.layout['orthographic']=True
        self.draw()
        self.assertEqual(self.c.nodes['target'],(-0.2,0.3,0.))
        self.assertEqual(self.c.nodes['cam'],(0.7,-0.1,0.))
    def test_preview_labels_match_new_direction(self):
        self.draw()
        self.assertEqual(self.c.draw_string,'目标 → 机位')
        for name in ('max_target_camera.py','max_target_camera_menu.py','使用说明.md'):
            text=(SOURCE/name).read_text(encoding='utf-8-sig')
            for obsolete in ('按下定机位','按下机位 → 拖出目标','按下位置为机位'):
                self.assertNotIn(obsolete,text,name)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(TargetFirstTests))
    OUT.mkdir(parents=True,exist_ok=True)
    report={'version':tool.VERSION,'tests_run':result.testsRun,'errors':len(result.errors),
            'failures':len(result.failures),'successful':result.wasSuccessful(),
            'scope':'callback unit tests with fake Maya commands; not real-pointer verification'}
    (OUT/'target_first_unit_tests.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    sys.exit(0 if result.wasSuccessful() else 1)
