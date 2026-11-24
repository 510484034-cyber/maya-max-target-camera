# -*- coding: utf-8 -*-
"""Drag into Maya to repair/load the installed menu, with a visible result."""
from __future__ import absolute_import, division, print_function, unicode_literals
import os
import sys
import traceback

try:
    _text_type=unicode
except NameError:
    _text_type=str


def load(notify=True):
    import maya.cmds as cmds
    original_path=list(sys.path)
    try:
        path=os.path.join(cmds.internalVar(userAppDir=True),'modules','MaxTargetCamera','scripts')
        if not os.path.isfile(os.path.join(path,'max_target_camera_menu.py')):
            raise RuntimeError('请先运行 install_max_target_camera.py 安装用户模块。')
        # Prefer installed files over an earlier copy imported by drag-and-drop.
        if path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0,path)
        old_menu=sys.modules.get('max_target_camera_menu')
        if old_menu is not None:
            old_menu.remove()
        # Reload from the installed directory, not from an outdated module.__file__.
        for name in ('max_target_camera_menu','max_target_camera'):
            sys.modules.pop(name,None)
        import max_target_camera
        import max_target_camera_menu
        result=max_target_camera_menu.install()
        if not result.get('installed'):
            raise RuntimeError('菜单未安装：' + str(result))
        print('[max目标相机] 创建 → 摄影机 → max目标相机；右侧方框打开设置。')
        if notify:
            answer=cmds.confirmDialog(title='max目标相机：加载成功',
                message='已添加：创建 → 摄影机 → max目标相机\n版本：'+max_target_camera.VERSION+'\n点击名称后在视口拖动创建；右侧方框打开设置。',
                button=['确定','打开设置'],defaultButton='确定',dismissString='确定')
            if answer=='打开设置':
                max_target_camera.show()
        return result
    except Exception as error:
        traceback.print_exc()
        if notify:
            cmds.confirmDialog(title='max目标相机：加载失败',
                message='菜单没有安装成功。\n\n'+_text_type(error)+'\n\n详细错误已输出到脚本编辑器。',
                button=['确定'],defaultButton='确定')
        raise
    finally:
        # Maya's drop handler pops its own path after returning. Preserve its stack.
        sys.path[:]=original_path


def onMayaDroppedPythonFile(*unused):
    load()
    return True


if __name__=='__main__':
    load()
