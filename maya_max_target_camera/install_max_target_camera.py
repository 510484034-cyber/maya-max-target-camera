# -*- coding: utf-8 -*-
"""Drag into Maya to install, or use mayapy with --maya-app-dir PATH.

Only this tool's module files are written. Existing userSetup.py/Maya.env and
Maya installation files are never changed. Disabling renames only our .mod file.
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import argparse
import datetime
import io
import json
import os
import shutil
import sys

VERSION = "1.4.1"
MODULE_NAME = "MaxTargetCamera"
MARKER = "managed-by-max-target-camera-installer-v1"
BASE = os.path.dirname(os.path.abspath(__file__))


def _read(path):
    with io.open(path, "r", encoding="utf-8-sig") as stream:
        return stream.read()


def _write(path, contents):
    with io.open(path, "w", encoding="utf-8", newline="\n") as stream:
        stream.write(contents)


def install_files(maya_app_dir, source_dir=None):
    source_dir = os.path.abspath(source_dir or BASE)
    app = os.path.abspath(maya_app_dir)
    modules = os.path.join(app, "modules")
    root = os.path.join(modules, MODULE_NAME)
    marker = os.path.join(root, "install_receipt.json")
    mod = os.path.join(modules, MODULE_NAME + ".mod")
    mapping = (("max_target_camera.py", "max_target_camera.py"),
               ("max_target_camera_menu.py", "max_target_camera_menu.py"),
               (os.path.join("startup", "userSetup.py"), "userSetup.py"))
    # Validate all sources and destination ownership before making changes.
    for source, destination in mapping:
        if not os.path.isfile(os.path.join(source_dir, source)):
            raise IOError("Missing package file: " + source)
    if os.path.exists(root):
        if not os.path.isfile(marker) or json.loads(_read(marker)).get("managed_by") != MARKER:
            raise RuntimeError("Destination already exists and is not managed by this installer: " + root)
    if os.path.exists(mod) and MARKER not in _read(mod):
        raise RuntimeError("Refusing to overwrite another module: " + mod)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    scripts = os.path.join(root, "scripts")
    if not os.path.isdir(scripts):
        os.makedirs(scripts)
    backups = []
    for source, destination in mapping:
        target = os.path.join(scripts, destination)
        if os.path.isfile(target):
            backup = os.path.join(root, "backups", stamp, destination)
            if not os.path.isdir(os.path.dirname(backup)):
                os.makedirs(os.path.dirname(backup))
            shutil.copy2(target, backup)
            backups.append(backup)
        shutil.copy2(os.path.join(source_dir, source), target)
    # Relative ASCII path is portable and avoids spaces/Unicode in module parsing.
    _write(mod, "# " + MARKER + "\n+ " + MODULE_NAME + " " + VERSION + " ./" + MODULE_NAME + "\nPYTHONPATH +:= scripts\n")
    receipt = {"managed_by":MARKER, "version":VERSION, "maya_app_dir":app,
               "module_file":mod, "module_root":root, "scripts_dir":scripts,
               "installed_files":[os.path.join(scripts, dest) for src, dest in mapping],
               "backups":backups, "modified_user_setup":False,
               "modified_maya_installation":False}
    _write(marker, json.dumps(receipt, ensure_ascii=False, indent=2))
    return receipt


def disable_files(maya_app_dir):
    mod = os.path.join(os.path.abspath(maya_app_dir), "modules", MODULE_NAME + ".mod")
    if not os.path.isfile(mod):
        return {"disabled":True, "already_disabled":True}
    if MARKER not in _read(mod):
        raise RuntimeError("Refusing to disable a module not managed by this tool: " + mod)
    destination = mod + ".disabled_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    os.rename(mod, destination)
    return {"disabled":True, "module_backup":destination, "scene_nodes_unchanged":True}


def install_current_maya():
    import maya.cmds as cmds
    receipt = install_files(cmds.internalVar(userAppDir=True))
    if receipt["scripts_dir"] not in sys.path:
        sys.path.insert(0, receipt["scripts_dir"])
    # Execute the newly installed version, not an earlier drag-drop import cache.
    for name in ("max_target_camera", "max_target_camera_menu"):
        if name in sys.modules:
            module = sys.modules[name]
            if name == "max_target_camera_menu":
                module.remove()
            del sys.modules[name]
    import max_target_camera_menu
    receipt["session"] = max_target_camera_menu.install()
    return receipt


def onMayaDroppedPythonFile(*unused):
    import maya.cmds as cmds
    answer = cmds.confirmDialog(title="安装 max目标相机菜单",
        message="添加到 创建 → 摄影机 → max目标相机。\n仅安装到用户 Maya 模块目录，适用于该目录下各版本。\n不改原 userSetup.py、Maya 安装文件或当前场景。是否安装？",
        button=["安装", "取消"], defaultButton="安装", cancelButton="取消", dismissString="取消")
    if answer != "安装":
        return False
    receipt = install_current_maya()
    print(json.dumps(receipt, ensure_ascii=True, indent=2))
    cmds.confirmDialog(title="安装完成", message="请打开 创建 → 摄影机 → max目标相机。\n右侧方框打开设置。重启后会自动添加菜单。", button=["确定"])
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install the Max target camera module for all Maya versions using a user app directory")
    parser.add_argument("--maya-app-dir", required=True)
    parser.add_argument("--disable", action="store_true")
    args = parser.parse_args()
    result = disable_files(args.maya_app_dir) if args.disable else install_files(args.maya_app_dir)
    print(json.dumps(result, ensure_ascii=True, indent=2))
