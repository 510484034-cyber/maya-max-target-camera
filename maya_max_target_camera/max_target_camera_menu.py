# -*- coding: utf-8 -*-
"""Native Create > Cameras integration. No installation-file edits or scene callbacks."""
from __future__ import absolute_import, division, print_function, unicode_literals
import json
import traceback
import maya.cmds as cmds
import maya.mel as mel
import maya.utils as utils
import max_target_camera as tool

LABEL = "max目标相机"
DOC_TAG = "maxTargetCamera/menu"
# Preserve original callbacks across importlib.reload during a tool update.
try:
    _hooks
except NameError:
    _hooks = {}


def _command(record):
    return cmds.menu if record["kind"] == "main" else cmds.menuItem


def _exists(record):
    return bool(_command(record)(record["menu"], exists=True))


def _run_original(original, source_type):
    if not original:
        return
    if callable(original):
        original()
    elif source_type == "python":
        exec(compile(original, "<original Maya menu callback>", "exec"), {})
    else:
        mel.eval(original)


def _bind(menu, kind):
    command = cmds.menu if kind == "main" else cmds.menuItem
    current = command(menu, query=True, postMenuCommand=True)
    for key, record in _hooks.items():
        if record["menu"] == menu and current == record["wrapper"]:
            return key
    key = str(len(_hooks) + 1)
    source_type = "mel"
    if kind != "main":
        source_type = command(menu, query=True, sourceType=True) or "mel"
    record = {"menu": menu, "kind": kind, "original": current,
              "source_type": source_type, "wrapper": None, "busy": False}
    _hooks[key] = record
    # A real Python callable removes MEL/python(...) language ambiguity.
    # Maya menu() strings entered through Python are not reliably MEL strings.
    def dispatch_callback(*unused):
        return _dispatch(key)
    command(menu, edit=True, postMenuCommand=dispatch_callback)
    record["callback"] = dispatch_callback
    record["wrapper"] = command(menu, query=True, postMenuCommand=True)
    return key


def _camera_submenus(main):
    try:
        localized = mel.eval('uiRes("m_ModCreateMenu.kCreateCameras")')
    except RuntimeError:
        localized = "Cameras"
    found = []
    for item in cmds.menu(main, query=True, itemArray=True) or []:
        if not cmds.menuItem(item, query=True, subMenu=True):
            continue
        label = cmds.menuItem(item, query=True, label=True)
        callback = tool._text(cmds.menuItem(item, query=True, postMenuCommand=True) or "")
        if ("ModCameraSubMenuItem" in callback or label == localized or
                label in ("Cameras", "摄影机", "摄像机")):
            found.append(item)
    return found


def _add_items(parent):
    # Parent is Maya's own Cameras submenu, not a new top-level menu.
    for item in cmds.menu(parent, query=True, itemArray=True) or []:
        if cmds.menuItem(item, query=True, docTag=True) == DOC_TAG + "/create":
            return item
    cmds.menuItem(parent=parent, divider=True, docTag=DOC_TAG + "/divider")
    item = cmds.menuItem(parent=parent, label=LABEL, image="cameraAim.png",
                        docTag=DOC_TAG + "/create", sourceType="python",
                        annotation="在视口按下定目标、拖动定机位；默认水平无翻滚。",
                        command=create_from_menu)
    cmds.menuItem(parent=parent, optionBox=True, docTag=DOC_TAG + "/options",
                  sourceType="python", annotation="max目标相机设置与控制器",
                  command=lambda *unused: tool.show())
    return item


def _dispatch(key):
    record = _hooks.get(key)
    if not record or not _exists(record) or record["busy"]:
        return
    record["busy"] = True
    try:
        _run_original(record["original"], record["source_type"])
        if record["kind"] == "main":
            for submenu in _camera_submenus(record["menu"]):
                _bind(submenu, "camera")
                _add_items(submenu)
        else:
            _add_items(record["menu"])
    finally:
        record["busy"] = False


def _main_create_menu_name():
    # A bare '$gMainCreateMenu;' is invalid MEL. The assignment returns its value.
    return mel.eval('global string $gMainCreateMenu; string $mtcMenuName; $mtcMenuName = $gMainCreateMenu;')


def install():
    """Install for this UI session. Native lazy menu rebuilding is preserved."""
    if cmds.about(batch=True):
        return {"installed":False, "reason":"batch mode"}
    main = _main_create_menu_name()
    if not main or not cmds.menu(main, exists=True):
        raise RuntimeError("Maya 创建菜单尚未就绪。请等待界面加载后再安装。")
    _dispatch(_bind(main, "main"))
    submenus = _camera_submenus(main)
    if not submenus:
        raise RuntimeError("未找到原生摄影机子菜单；未添加其他位置的替代菜单。")
    return {"installed":True, "label":LABEL, "parent_menus":submenus, "version":tool.VERSION}


def remove():
    """Remove only our menu entries and restore callbacks we still own."""
    removed = 0
    for record in list(_hooks.values()):
        if not _exists(record):
            continue
        command = _command(record)
        current = command(record["menu"], query=True, postMenuCommand=True)
        if current == record["wrapper"]:
            original = record["original"] or ""
            if record["kind"] == "main" and not callable(original) and record["source_type"] == "mel":
                # Restore Autodesk's original top-level MEL callback as MEL.
                mel.eval("menu -edit -postMenuCommand {0} {1};".format(
                    json.dumps(original), json.dumps(record["menu"])))
            else:
                flags = {"edit": True, "postMenuCommand": original}
                if record["kind"] != "main":
                    flags["sourceType"] = record["source_type"]
                command(record["menu"], **flags)
        if record["kind"] == "camera":
            for item in cmds.menu(record["menu"], query=True, itemArray=True) or []:
                if (cmds.menuItem(item, query=True, docTag=True) or "").startswith(DOC_TAG + "/"):
                    cmds.deleteUI(item)
                    removed += 1
    _hooks.clear()
    return removed


def create_from_menu(*unused):
    """Menu defaults to mouse-drag placement; settings offer a one-click fallback."""
    try:
        return tool.start_interactive(name="MaxTarget")
    except Exception as error:
        cmds.warning("[max目标相机] 拖动工具暂不可用，改为在视野内创建：" + tool._text(error))
        try:
            info = tool.create_near_view(name="MaxTarget")
            if tool._ui is not None and cmds.window(tool.WINDOW, exists=True):
                tool._ui.refresh(info["root"])
            return info
        except Exception as fallback:
            cmds.warning("[max目标相机] 创建失败：" + tool._text(fallback))
            return None


def startup(attempt=0):
    if cmds.about(batch=True):
        return
    try:
        install()
    except Exception:
        if attempt < 2:
            utils.executeDeferred(lambda: startup(attempt + 1))
        else:
            cmds.warning("[max目标相机] 菜单安装未完成；可在 Python 页运行 max_target_camera_menu.install()。")
            traceback.print_exc()
