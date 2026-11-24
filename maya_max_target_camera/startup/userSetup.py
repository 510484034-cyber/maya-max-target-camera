# -*- coding: utf-8 -*-
# This belongs ONLY to the MaxTargetCamera module; never overwrite a user's userSetup.py.
from __future__ import absolute_import, division, print_function, unicode_literals

def _max_target_camera_deferred_startup():
    try:
        import maya.cmds as _mtc_cmds
        if not _mtc_cmds.about(batch=True):
            import maya.utils as _mtc_utils
            import max_target_camera_menu as _mtc_menu
            _mtc_utils.executeDeferred(_mtc_menu.startup)
    except Exception:
        import traceback as _mtc_traceback
        _mtc_traceback.print_exc()

_max_target_camera_deferred_startup()
