"""Display-only parameter and default-keying policy tests, without a Maya runtime."""
import importlib.util
import math
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
_MAYA = types.ModuleType('maya')
_MAYA.cmds = types.ModuleType('maya.cmds')
spec = importlib.util.spec_from_file_location('mtc_display_tests', ROOT/'maya_max_target_camera/max_target_camera.py')
tool = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'maya': _MAYA, 'maya.cmds': _MAYA.cmds}):
    spec.loader.exec_module(tool)

INFO = {'root':'rig','camera':'camera','target':'target','shape':'cameraShape','up':'up'}
class FakeCommands:
    def __init__(self):
        self.values = {'cameraShape.locatorScale':1.0,'target.displaySize':1.0}
        self.radius = 1.0
        self.locked = set()
        self.driven = set()
        self.animated = set()
        self.keys_here = set()
        self.writes = []
        self.key_calls = []
        self.tangent_queries = []
        self.defaults = {'inTangentType':'auto','outTangentType':'auto'}
        self.fail_once = None
    def attributeQuery(self,*a,**kw):return True
    def listRelatives(self,node,**kw):return ['display'] if kw.get('noIntermediate') else ['base','display']
    def nodeType(self,node):return 'nurbsCurve'
    def getAttr(self,plug,**kw):
        if kw.get('lock'):return plug in self.locked
        if plug.endswith('.intermediateObject'):return plug.startswith('base.')
        return self.values[plug]
    def xform(self,*a,**kw):
        return [-self.radius,-self.radius,-self.radius,self.radius,self.radius,self.radius]
    def listConnections(self,plug,**kw):return ['driver.output'] if plug in self.driven else []
    def keyframe(self,node,**kw):
        if 'attribute' in kw:return int(node+'.'+kw['attribute'] in self.keys_here)
        return int(node in self.animated)
    def undoInfo(self,**kw):pass
    def pointPosition(self,*a,**kw):return (0,0,0)
    def setAttr(self,plug,value):
        self.writes.append((plug,value));self.values[plug]=value
        if self.fail_once==plug:
            self.fail_once=None;raise RuntimeError('Injected setAttr error')
    def currentTime(self,**kw):return 10.0
    def keyTangent(self,**kw):
        self.tangent_queries.append(kw)
        assert kw.get('query') and kw.get('g')
        for name in self.defaults:
            if kw.get(name):return [self.defaults[name]]
    def setKeyframe(self,node,**kw):self.key_calls.append((node,kw))

class DisplayAndKeyingTests(unittest.TestCase):
    def setUp(self):
        self.cmds = FakeCommands()
        self.patches = [patch.object(tool,'cmds',self.cmds),patch.object(tool,'rig_info',lambda node:INFO)]
        for p in self.patches:p.start();self.addCleanup(p.stop)
    def test_native_reference_defaults_are_one(self):
        self.assertEqual(tool.DEFAULT_CAMERA_ICON_SCALE,1.0)
        self.assertEqual(tool.DEFAULT_TARGET_HALF_EXTENT,1.0)
    def test_resize_writes_only_display_source_channels(self):
        result=tool.set_display_scales('rig',camera=5,target=7)
        self.assertEqual(result,{'camera':5,'target':7})
        self.assertEqual(set(p for p,v in self.cmds.writes),{'cameraShape.locatorScale','target.displaySize'})
    def test_camera_resize_does_not_touch_target(self):
        tool.set_display_scales('rig',camera=8)
        self.assertEqual(self.cmds.writes,[('cameraShape.locatorScale',8)])
    def test_old_tiny_target_is_normalized_without_scaling_the_transform(self):
        self.cmds.radius=.004
        result=tool.reset_display_scales('rig')
        self.assertEqual(result,{'camera':1,'target':1})
        self.assertEqual(self.cmds.values['target.displaySize'],250)
    def test_half_and_double_use_current_display_values(self):
        tool.scale_display('rig',2);tool.scale_display('rig',.5)
        self.assertEqual(tool.display_scales('rig'),{'camera':1,'target':1})
    def test_invalid_values_are_atomic(self):
        for value in (0,-1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):tool.set_display_scales('rig',camera=2,target=value)
        self.assertEqual(self.cmds.writes,[])
    def test_locked_driven_or_keyed_display_is_never_overwritten(self):
        for field in ('locked','driven','animated'):
            collection=getattr(self.cmds,field);collection.add('target.displaySize')
            with self.assertRaises(ValueError):tool.set_display_scales('rig',camera=2,target=3)
            collection.clear()
        self.assertEqual(self.cmds.writes,[])
    def test_unexpected_second_write_failure_rolls_back_both(self):
        self.cmds.fail_once='target.displaySize'
        with self.assertRaises(RuntimeError):tool.set_display_scales('rig',camera=3,target=5)
        self.assertEqual(tool.display_scales('rig'),{'camera':1,'target':1})
    def test_maya_defaults_are_only_read(self):
        self.assertEqual(tool.default_key_tangents(),self.cmds.defaults)
        self.assertEqual(len(self.cmds.tangent_queries),2)
        self.assertTrue(all(c.get('query') and c.get('g') for c in self.cmds.tangent_queries))
    def test_new_keys_explicitly_follow_maya_defaults(self):
        self.cmds.defaults={'inTangentType':'linear','outTangentType':'step'}
        with patch.object(tool,'_key_specs',lambda info:[('camera',['translateX','rotateZ'])]):
            result=tool.key_controls('rig')
        self.assertEqual(result,self.cmds.defaults)
        self.assertEqual(len(self.cmds.key_calls),1)
        self.assertEqual(self.cmds.key_calls[0][1]['outTangentType'],'step')
    def test_existing_keys_are_not_forced_to_new_tangents(self):
        self.cmds.keys_here.add('camera.rotateZ')
        with patch.object(tool,'_key_specs',lambda info:[('camera',['translateX','rotateZ'])]):
            tool.key_controls('rig')
        calls={tuple(kw['attribute']):kw for node,kw in self.cmds.key_calls}
        self.assertNotIn('inTangentType',calls[('rotateZ',)])
        self.assertEqual(calls[('translateX',)]['inTangentType'],'auto')
    def test_legacy_camera_only_scaling_does_not_require_a_target_driver(self):
        self.cmds.attributeQuery=lambda attr, **kw: attr != 'displaySize'
        self.assertEqual(tool.set_display_scales('rig',camera=4),{'camera':4})
        self.assertEqual(self.cmds.writes,[('cameraShape.locatorScale',4)])
        with self.assertRaises(ValueError):tool.reset_display_scales('rig')
        self.assertEqual(self.cmds.values['cameraShape.locatorScale'],4)
    def test_display_resize_does_not_call_any_animation_api(self):
        tool.set_display_scales('rig',camera=3,target=9)
        self.assertFalse(self.cmds.key_calls)
        self.assertFalse(self.cmds.tangent_queries)

if __name__=='__main__':unittest.main(verbosity=2)
