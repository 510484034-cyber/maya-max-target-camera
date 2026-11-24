# -*- coding: utf-8 -*-
"""Portable Max-style target camera; targets Maya 2018+ / Python 2.7 and 3.

Drag this file into a Maya viewport to open the tool. No installation, plug-in,
expression, scriptNode, or background callback is needed by the saved rig.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from contextlib import contextmanager
import math
import re
import sys

import maya.cmds as cmds

VERSION = "1.4.1"
MIN_TARGET_YEAR = 2018
MAX_TARGET_YEAR = 2026
REQUIRED_NODE_TYPES = ("transform", "camera", "nurbsCurve", "aimConstraint",
                       "distanceBetween", "pointMatrixMult", "composeMatrix", "transformGeometry", "condition")
WINDOW = "MaxTargetCameraToolWindow"
TAG = "mtcVersion"
OWNER = "mtcOwner"
PARTS = {"camera": "mtcCamera", "target": "mtcTarget", "up": "mtcUp", "guide": "mtcGuide"}
CAMERA_ATTRS = (
    "focalLength", "horizontalFilmAperture", "verticalFilmAperture",
    "horizontalFilmOffset", "verticalFilmOffset", "lensSqueezeRatio",
    "filmFit", "filmFitOffset", "nearClipPlane", "farClipPlane",
    "cameraScale", "overscan", "shutterAngle", "fStop", "focusDistance",
    "depthOfField", "filmRollValue", "filmRollOrder", "filmTranslateH",
    "filmTranslateV", "horizontalRollPivot", "verticalRollPivot",
    "preScale", "postScale", "panZoomEnabled", "renderPanZoom",
    "horizontalPan", "verticalPan", "zoom", "displayResolution",
    "displayFilmGate", "displayGateMask", "displaySafeAction", "displaySafeTitle",
)
_last_panel = None
_ui = None
DRAW_CONTEXT = "MaxTargetCameraDrawContext"
_draw_tool = None
try:
    text_type = unicode
except NameError:
    text_type = str


def _text(value):
    """Keep Chinese UI, paths and error messages safe under Python 2 and 3."""
    if isinstance(value, text_type):
        return value
    if isinstance(value, bytes):
        for encoding in ("utf-8", sys.getfilesystemencoding() or "utf-8"):
            try:
                return value.decode(encoding)
            except (UnicodeError, LookupError):
                pass
        return value.decode("utf-8", "replace")
    try:
        return text_type(value)
    except UnicodeError:
        return _text(repr(value))


def _is_finite(value):
    # math.isfinite is unavailable in Maya's Python 2.7 builds.
    return not (math.isnan(value) or math.isinf(value))


def compatibility_report():
    """Read-only capability checks; a passing check is NOT version certification."""
    api_version = int(cmds.about(apiVersion=True))
    maya_year = api_version // 10000
    node_types = set(cmds.allNodeTypes() or [])
    missing = sorted(set(REQUIRED_NODE_TYPES) - node_types)
    py = sys.version_info[:3]
    language_ok = (py[0] == 2 and py[1] >= 7) or py[0] == 3
    return {
        "tool_version": VERSION,
        "maya_version": _text(cmds.about(version=True)),
        "maya_api_version": api_version,
        "maya_year": maya_year,
        "python_version": ".".join(_text(n) for n in py),
        "platform": sys.platform,
        "target_year_range": [MIN_TARGET_YEAR, MAX_TARGET_YEAR],
        "in_target_range": MIN_TARGET_YEAR <= maya_year <= MAX_TARGET_YEAR,
        "missing_node_types": missing,
        "capability_check_passed": language_ok and not missing,
        "external_python_packages": [],
        "qt_binding_required": False,
        "note": "能力自检不等于该版本已经实测；实测范围请查看 使用说明.md。",
    }


def _preflight():
    report = compatibility_report()
    if not report["capability_check_passed"]:
        raise RuntimeError("当前环境缺少必要节点或 Python 不兼容：" +
                           ", ".join(report["missing_node_types"]))
    if not report["in_target_range"]:
        cmds.warning("此 Maya 年份不在 2018–2026 的兼容目标内；将按节点能力尝试运行，尚无版本保证。")
    return report


def _cross(a, b):
    return (a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0])


def _up_matrix(up, position):
    """A right-handed row-vector matrix; local Y maps to up, without API bindings."""
    y = _unit(_v3(up))
    reference = (0.0, 0.0, 1.0) if abs(y[2]) < 0.9 else (1.0, 0.0, 0.0)
    x = _unit(_cross(y, reference))
    z = _unit(_cross(x, y))
    return list(x) + [0.0] + list(y) + [0.0] + list(z) + [0.0] + list(_v3(position)) + [1.0]


@contextmanager
def _undo(label):
    cmds.undoInfo(openChunk=True, chunkName=label)
    try:
        yield
    finally:
        cmds.undoInfo(closeChunk=True)


def _v3(value):
    value = tuple(float(x) for x in value)
    if len(value) != 3 or not all(_is_finite(x) for x in value):
        raise ValueError("位置或方向必须是三个有限数值。")
    return value


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _length(v):
    return math.sqrt(sum(x * x for x in v))


def _unit(v):
    length = _length(v)
    if length < 1e-8:
        raise ValueError("相机不能与目标重合，上方向也不能为零。")
    return tuple(x / length for x in v)


def _world_position(node):
    return tuple(cmds.xform(node, query=True, worldSpace=True, translation=True))


def _long(node):
    found = cmds.ls(node, long=True) or []
    if len(found) != 1:
        raise ValueError("节点不存在或名称不唯一：" + _text(node))
    return found[0]


def _camera_parts(node):
    node = _long(node)
    if cmds.nodeType(node) == "camera":
        return (cmds.listRelatives(node, parent=True, fullPath=True)[0], node)
    shapes = cmds.listRelatives(node, shapes=True, noIntermediate=True,
                                type="camera", fullPath=True) or []
    if len(shapes) != 1:
        raise ValueError("请选择一个普通 Maya 摄像机。")
    return node, shapes[0]


def _snapshot_camera(node):
    transform, shape = _camera_parts(node)
    if cmds.getAttr(shape + ".orthographic"):
        raise ValueError("当前是正交视图，请先切换到透视视图或透视摄像机。")
    matrix = cmds.xform(transform, query=True, worldSpace=True, matrix=True)
    return {
        "position": _world_position(transform),
        "forward": _unit(tuple(-matrix[i] for i in (8, 9, 10))),
        "up": _unit(tuple(matrix[i] for i in (4, 5, 6))),
        "distance": max(float(cmds.getAttr(shape + ".centerOfInterest")), 0.001),
        "attrs": {a: cmds.getAttr(shape + "." + a) for a in CAMERA_ATTRS
                  if cmds.attributeQuery(a, node=shape, exists=True)},
    }


def _name_stem(name):
    name = re.sub(r"[^A-Za-z0-9_]", "_", _text(name).strip()).strip("_") or "MaxTarget"
    if name[0].isdigit():
        name = "Cam_" + name
    for number in range(1, 100000):
        stem = "{}_{:03d}".format(name, number)
        if not cmds.ls(":" + stem + "_*", recursive=True):
            return stem
    raise ValueError("同名相机过多，请换一个名称。")


def _lock(node, attrs):
    for attr in attrs:
        cmds.setAttr(node + "." + attr, lock=True, keyable=False, channelBox=False)


def _color(node, rgb, fallback_index=17):
    for shape in cmds.listRelatives(node, shapes=True, fullPath=True) or []:
        cmds.setAttr(shape + ".overrideEnabled", True)
        if (cmds.attributeQuery("overrideRGBColors", node=shape, exists=True) and
                cmds.attributeQuery("overrideColorRGB", node=shape, exists=True)):
            cmds.setAttr(shape + ".overrideRGBColors", True)
            cmds.setAttr(shape + ".overrideColorRGB", *rgb, type="double3")
        else:
            cmds.setAttr(shape + ".overrideColor", fallback_index)


def _link(root, node, part=None, index=None):
    cmds.addAttr(node, longName=OWNER, attributeType="message")
    cmds.connectAttr(root + ".message", node + "." + OWNER)
    if part:
        plug = PARTS[part]
        cmds.addAttr(root, longName=plug, attributeType="message")
        cmds.connectAttr(node + ".message", root + "." + plug)
    elif index is not None:
        cmds.connectAttr(node + ".message", "{}.mtcUtilities[{}]".format(root, index))


def resolve_rig(node):
    """Resolve via message connections, not names; survives rename and namespaces."""
    node = _long(node)
    if cmds.attributeQuery(TAG, node=node, exists=True):
        return node
    if cmds.attributeQuery(OWNER, node=node, exists=True):
        owner = cmds.listConnections(node + "." + OWNER, source=True, destination=False) or []
        if len(owner) == 1 and cmds.attributeQuery(TAG, node=owner[0], exists=True):
            return _long(owner[0])
    parents = cmds.listRelatives(node, parent=True, fullPath=True) or []
    if parents:
        return resolve_rig(parents[0])
    raise ValueError("所选节点不属于本工具创建的目标摄像机。")


def rig_info(node):
    root = resolve_rig(node)
    info = {"root": root}
    for key, plug in PARTS.items():
        members = cmds.listConnections(root + "." + plug, source=True, destination=False) or []
        if len(members) != 1:
            raise ValueError("相机组缺少 {}，可能有成员被手动删除。".format(key))
        info[key] = _long(members[0])
    info["shape"] = _camera_parts(info["camera"])[1]
    return info


def list_rigs():
    nodes = cmds.ls("*." + TAG, objectsOnly=True, recursive=True, long=True) or []
    return sorted(set(nodes))


def selection_center():
    selection = cmds.ls(selection=True, long=True) or []
    if not selection:
        raise ValueError("请先选中要拍摄的物体，或取消“目标放到所选物体中心”。")
    bbox = cmds.exactWorldBoundingBox(selection, ignoreInvisible=False)
    return tuple((bbox[i] + bbox[i + 3]) * 0.5 for i in range(3))


def _proxy(node, name, source, label):
    """A native proxy leaves the real camera parameter editable in the AE."""
    cmds.addAttr(node, longName=name, niceName=label, proxy=source, keyable=True)


def _scene_up():
    return (0.0, 0.0, 1.0) if cmds.upAxis(query=True, axis=True) == "z" else (0.0, 1.0, 0.0)


def _horizon_control(camera, aim, stem, created, enabled):
    # World-up type 0 uses the scene up axis, independently of the captured
    # viewport tilt or the rig parent's rotation. Local rotateZ remains a
    # separate user-owned roll input; movement never writes or keys it.
    if not cmds.attributeQuery("horizonLock", node=camera, exists=True):
        cmds.addAttr(camera, longName="horizonLock", niceName="Keep Horizon Level",
                     attributeType="bool", defaultValue=bool(enabled))
        cmds.setAttr(camera + ".horizonLock", channelBox=True)
    mode = cmds.createNode("condition", name=stem + "_HorizonMode")
    created.append(mode)
    cmds.setAttr(mode + ".operation", 0)
    cmds.setAttr(mode + ".secondTerm", 1)
    cmds.setAttr(mode + ".colorIfTrueR", 0)  # aimConstraint: scene up
    cmds.setAttr(mode + ".colorIfFalseR", 2)  # explicit manual UP control
    cmds.connectAttr(camera + ".horizonLock", mode + ".firstTerm")
    cmds.connectAttr(mode + ".outColorR", aim + ".worldUpType", force=True)
    return mode


def _ensure_horizon_control(info, enabled=True):
    camera, root = info["camera"], info["root"]
    if cmds.referenceQuery(root, isNodeReferenced=True):
        raise ValueError("请在引用相机的源文件中修复地平线。")
    if not cmds.attributeQuery("horizonLock", node=camera, exists=True):
        utilities = cmds.listConnections(root + ".mtcUtilities", source=True, destination=False) or []
        aims = [n for n in utilities if cmds.nodeType(n) == "aimConstraint"]
        if len(aims) != 1:
            raise ValueError("相机约束已被自定义，不能安全修改上方向。")
        if cmds.listConnections(aims[0] + ".worldUpType", source=True, destination=False):
            raise ValueError("上方向模式已有自定义驱动，保留原接线。")
        stem = root.rsplit("|", 1)[-1].rsplit("_RIG", 1)[0]
        mode = _horizon_control(camera, aims[0], stem, [], enabled)
        indices = cmds.getAttr(root + ".mtcUtilities", multiIndices=True) or []
        _link(root, mode, index=max(indices + [-1]) + 1)
    cmds.setAttr(camera + ".horizonLock", bool(enabled))


def level_horizon(node, reset_unkeyed_roll=True):
    """Explicit repair: world-up lock; preserve all keyed/driven roll inputs."""
    info = rig_info(node)
    with _undo("Keep Target Camera Horizon Level"):
        _ensure_horizon_control(info, True)
        camera = info["camera"]
        # v1.3+ roll is a proxy for rz; older rigs have an independent roll attr.
        plug = camera + (".rotateZ" if cmds.getAttr(camera + ".rotateOrder") == 2 else ".roll")
        keys = cmds.keyframe(plug, query=True, keyframeCount=True) or 0
        sources = cmds.listConnections(plug, source=True, destination=False, plugs=True) or []
        roll_preserved = bool(keys or sources)
        if reset_unkeyed_roll and not roll_preserved and not cmds.getAttr(plug, lock=True):
            cmds.setAttr(plug, 0)
        film = info["shape"] + ".filmRollValue"
        if (reset_unkeyed_roll and not cmds.getAttr(film, lock=True)
                and not cmds.listConnections(film, source=True, destination=False)
                and not (cmds.keyframe(film, query=True, keyframeCount=True) or 0)):
            cmds.setAttr(film, 0)
        return {"roll_animation_preserved": roll_preserved, "horizon_locked": True}


def _aim_with_editable_roll(root, camera, target, up, stem, created, keep_horizon=False):
    # In ZXY order, local Z roll precedes the solved X/Y aim. The solver's
    # remaining Z twist goes in rotateAxisZ, so ordinary rotateZ stays editable.
    # This graph has no camera.worldMatrix -> solver -> camera cycle.
    solver = cmds.createNode("transform", name=stem + "_AimSolver", parent=root)
    created.append(solver)
    cmds.setAttr(solver + ".visibility", False)
    if cmds.attributeQuery("hiddenInOutliner", node=solver, exists=True):
        cmds.setAttr(solver + ".hiddenInOutliner", True)
    for node in (solver, camera):
        cmds.setAttr(node + ".rotateOrder", 2)  # ZXY, available in older Maya too.
    cmds.connectAttr(camera + ".translate", solver + ".translate")
    aim = cmds.aimConstraint(target, solver, name=stem + "_Aim",
                             maintainOffset=False, aimVector=(0, 0, -1),
                             upVector=(0, 1, 0), worldUpType="objectrotation",
                             worldUpObject=up, worldUpVector=(0, 1, 0))[0]
    created.append(aim)
    cmds.connectAttr(solver + ".rotateX", camera + ".rotateX")
    cmds.connectAttr(solver + ".rotateY", camera + ".rotateY")
    cmds.connectAttr(solver + ".rotateZ", camera + ".rotateAxisZ")
    cmds.setAttr(camera + ".rotateZ", keyable=True, lock=False)
    _lock(camera, ("rotateX", "rotateY", "rotateOrder", "rotateAxisX",
                   "rotateAxisY", "rotateAxisZ"))
    mode = _horizon_control(camera, aim, stem, created, keep_horizon)
    return [solver, aim, mode]


def _target_display(target, camera, stem, created):
    # Scale only the drawn curve, never the control's position or camera rig.
    # Dimensionless scaling avoids cm/m unit-conversion mistakes.
    base = cmds.listRelatives(target, shapes=True, fullPath=True)[0]
    cmds.setAttr(base + ".intermediateObject", True)
    display = cmds.createNode("nurbsCurve", name=stem + "_TargetDisplayShape", parent=target)
    created.append(display)
    matrix = cmds.createNode("composeMatrix", name=stem + "_TargetDisplayMatrix")
    created.append(matrix)
    geometry = cmds.createNode("transformGeometry", name=stem + "_TargetDisplayGeometry")
    created.append(geometry)
    cmds.addAttr(target, longName="displaySize", niceName="Target Size",
                 attributeType="double", minValue=0.001, defaultValue=1.0, keyable=True)
    for axis in "XYZ":
        cmds.connectAttr(target + ".displaySize", matrix + ".inputScale" + axis)
    cmds.connectAttr(base + ".local", geometry + ".inputGeometry")
    cmds.connectAttr(matrix + ".outputMatrix", geometry + ".transform")
    cmds.connectAttr(geometry + ".outputGeometry", display + ".create")
    # Ensure immediate bbox/selection queries see evaluated curve data.
    cmds.getAttr(display + ".spans")
    _proxy(camera, "targetSize", target + ".displaySize", "Target Size")
    return [matrix, geometry]


def create_camera(name="MaxTarget", camera_position=None, target_position=None,
                  up_vector=None, source_camera=None, focal_length=None, keep_horizon=True):
    """Create only new nodes. Positions/distances use the current Maya scene unit.

    source_camera copies its evaluated pose/lens at this frame, NOT animation.
    Returns message-resolved full DAG paths. One undo removes the new rig.
    """
    _preflight()
    source = _snapshot_camera(source_camera) if source_camera else None
    position = _v3(camera_position if camera_position is not None else
                   (source["position"] if source else (4.0, 2.0, 5.0)))
    if target_position is None:
        target_position = (tuple(position[i] + source["forward"][i] * source["distance"]
                                 for i in range(3)) if source else (0.0, 0.0, 0.0))
    target_position = _v3(target_position)
    forward = _unit(_sub(target_position, position))
    distance = _length(_sub(target_position, position))
    if up_vector is None:
        up_vector = _scene_up() if keep_horizon else (source["up"] if source else _scene_up())
    up_vector = _unit(_v3(up_vector))
    if not keep_horizon and abs(sum(a * b for a, b in zip(forward, up_vector))) > 0.999:
        up_vector = min(((0, 1, 0), (0, 0, 1), (1, 0, 0)),
                        key=lambda v: abs(sum(a * b for a, b in zip(v, forward))))
        cmds.warning("镜头接近上方向，创建时已换用不平行的上方向。可选择 UP 控制器继续调整。")
    lens = float(focal_length if focal_length is not None else
                 (source["attrs"]["focalLength"] if source else 35.0))
    if not _is_finite(lens) or lens < 0.1:
        raise ValueError("焦距必须是至少 0.1 毫米的有限数值。")
    stem = _name_stem(name)
    size = max(distance * 0.008, 0.0001)
    target_size = max(distance * 0.004, 0.0001)
    created = []
    skipped_camera_attrs = []
    old_selection = cmds.ls(selection=True, long=True) or []
    previous_namespace = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)

    with _undo("Create Max Target Camera"):
        try:
            # Work at the root namespace, and restore the user's namespace even on failure.
            cmds.namespace(setNamespace=":")
            root = cmds.createNode("transform", name=stem + "_RIG")
            created.append(root)
            cmds.addAttr(root, longName=TAG, dataType="string")
            cmds.setAttr(root + "." + TAG, VERSION, type="string", lock=True)
            cmds.addAttr(root, longName="mtcUtilities", attributeType="message", multi=True)
            # A handle at the target pivot can select the ENTIRE rig by mistake.
            cmds.setAttr(root + ".displayHandle", False)
            camera, shape = cmds.camera(name=stem + "_CAM")
            created.append(camera)
            camera = cmds.parent(camera, root)[0]
            shape = cmds.listRelatives(camera, shapes=True, fullPath=True)[0]
            cmds.xform(camera, worldSpace=True, translation=position)
            if source:
                for attr, value in source["attrs"].items():
                    if not cmds.attributeQuery(attr, node=shape, exists=True):
                        skipped_camera_attrs.append(attr)
                        continue
                    try:
                        cmds.setAttr(shape + "." + attr, value)
                    except (RuntimeError, TypeError):
                        skipped_camera_attrs.append(attr)
                if skipped_camera_attrs:
                    cmds.warning("以下相机参数在此环境中未能复制：" + ", ".join(skipped_camera_attrs))
            if keep_horizon:
                cmds.setAttr(shape + ".filmRollValue", 0)
            cmds.setAttr(shape + ".focalLength", lens)
            cmds.setAttr(shape + ".renderable", False)
            cmds.setAttr(shape + ".locatorScale", size)

            corners = [(-1,-1,-1), (-1,-1,1), (1,-1,1), (1,-1,-1), (-1,-1,-1),
                       (-1,1,-1), (-1,1,1), (-1,-1,1), (-1,1,1), (1,1,1),
                       (1,-1,1), (1,1,1), (1,1,-1), (1,-1,-1), (1,1,-1), (-1,1,-1)]
            target = cmds.curve(name=stem + "_TARGET", degree=1,
                                point=[tuple(x * target_size for x in p) for p in corners])
            created.append(target)
            target = cmds.parent(target, root)[0]
            cmds.xform(target, worldSpace=True, translation=target_position)
            _color(target, (0.35, 1.0, 0.4), 14)

            up = cmds.curve(name=stem + "_UP", degree=1,
                            point=[(0,0,0), (0,3*size,0), (-size,2*size,0),
                                   (0,3*size,0), (size,2*size,0)])
            created.append(up)
            up = cmds.parent(up, root)[0]
            up_position = [target_position[i] + up_vector[i] * size * 5 for i in range(3)]
            matrix = _up_matrix(up_vector, up_position)
            cmds.xform(up, worldSpace=True, matrix=matrix)
            _color(up, (1.0, 0.7, 0.12), 17)

            aim_nodes = _aim_with_editable_roll(root, camera, target, up, stem, created, keep_horizon)
            _proxy(camera, "roll", camera + ".rotateZ", "Roll")
            _proxy(camera, "lens", shape + ".focalLength", "Lens (mm)")
            _proxy(camera, "iconScale", shape + ".locatorScale", "Camera Icon Scale")
            display_nodes = _target_display(target, camera, stem, created)
            _color(target, (0.35, 1.0, 0.4), 14)
            measurement = cmds.createNode("distanceBetween", name=stem + "_Distance")
            created.append(measurement)
            cmds.connectAttr(camera + ".worldMatrix[0]", measurement + ".inMatrix1")
            cmds.connectAttr(target + ".worldMatrix[0]", measurement + ".inMatrix2")
            cmds.connectAttr(measurement + ".distance", shape + ".centerOfInterest", force=True)
            cmds.addAttr(camera, longName="targetDistance", niceName="Target Distance (readout)",
                         attributeType="doubleLinear")
            cmds.connectAttr(measurement + ".distance", camera + ".targetDistance")
            cmds.setAttr(camera + ".targetDistance", channelBox=True, lock=True)

            guide = cmds.curve(name=stem + "_GUIDE", degree=1, point=[(0,0,0), (0,0,0)])
            created.append(guide)
            guide = cmds.parent(guide, root)[0]
            guide_shape = cmds.listRelatives(guide, shapes=True, fullPath=True)[0]
            _color(guide, (0.25, 0.7, 1.0), 18)
            cmds.setAttr(guide_shape + ".overrideDisplayType", 2)
            utilities = aim_nodes + display_nodes + [measurement]
            for index, endpoint in enumerate((camera, target)):
                # Long-standing core nodes; no decomposeMatrix/API/Qt dependency.
                world_point = cmds.createNode("pointMatrixMult", name=stem + "_GuideWorld" + _text(index))
                created.append(world_point)
                local_point = cmds.createNode("pointMatrixMult", name=stem + "_GuideLocal" + _text(index))
                created.append(local_point)
                cmds.setAttr(world_point + ".vectorMultiply", False)
                cmds.setAttr(local_point + ".vectorMultiply", False)
                cmds.connectAttr(endpoint + ".worldMatrix[0]", world_point + ".inMatrix")
                cmds.connectAttr(world_point + ".output", local_point + ".inPoint")
                cmds.connectAttr(guide + ".worldInverseMatrix[0]", local_point + ".inMatrix")
                cmds.connectAttr(local_point + ".output", "{}.controlPoints[{}]".format(guide_shape, index))
                utilities.extend([world_point, local_point])
            for attr, controlled, default in (("showGuide", guide, True), ("showUp", up, False)):
                cmds.addAttr(camera, longName=attr, attributeType="bool", defaultValue=default)
                cmds.setAttr(camera + "." + attr, channelBox=True)
                cmds.connectAttr(camera + "." + attr, controlled + ".visibility")
            for part, node in (("camera", camera), ("target", target), ("up", up), ("guide", guide)):
                _link(root, node, part=part)
            for index, node in enumerate(utilities):
                _link(root, node, index=index)
            rotate = ("rx", "ry", "rz")
            scale = ("sx", "sy", "sz")
            translate = ("tx", "ty", "tz")
            _lock(camera, scale)
            # Target rotation/scale affect only its display, never the camera position.
            _lock(up, translate + scale)
            _lock(guide, translate + rotate + scale)
            _lock(root, scale)
            cmds.xform(root, worldSpace=True, pivots=target_position)
            result = rig_info(root)
            result["skipped_camera_attrs"] = skipped_camera_attrs
            cmds.select(result["camera"], replace=True)
            return result
        except Exception:
            # Delete only this call's new nodes, never the user's source camera.
            for node in reversed(created):
                if cmds.objExists(node):
                    cmds.delete(node)
            remaining = [n for n in old_selection if cmds.objExists(n)]
            cmds.select(remaining, replace=True) if remaining else cmds.select(clear=True)
            raise
        finally:
            cmds.namespace(setNamespace=previous_namespace)


def select_part(node, part):
    info = rig_info(node)
    if part not in ("root", "camera", "target", "up"):
        raise ValueError("不支持的控制器：" + _text(part))
    with _undo("Select Target Camera Control"):
        if part == "root":
            # Recenter the orbit pivot without moving any object.
            cmds.xform(info["root"], worldSpace=True, pivots=_world_position(info["target"]), preserve=True)
        if part == "up":
            # Choosing the explicit UP control is an intentional manual override.
            _ensure_horizon_control(info, False)
            cmds.setAttr(info["camera"] + ".showUp", True)
        cmds.selectMode(object=True)
        cmds.select(info[part], replace=True, noExpand=True)
        if not cmds.about(batch=True):
            cmds.setToolTo("RotateSuperContext" if part == "up" else "moveSuperContext")
    return info[part]


def dolly(node, factor):
    factor = float(factor)
    if not _is_finite(factor) or factor <= 0:
        raise ValueError("推拉比例必须大于零。")
    info = rig_info(node)
    target = _world_position(info["target"])
    offset = _sub(_world_position(info["camera"]), target)
    if _length(offset) * factor < 1e-5:
        raise ValueError("相机已过于接近目标，不能继续推近。")
    with _undo("Dolly Target Camera"):
        cmds.xform(info["camera"], worldSpace=True,
                   translation=tuple(target[i] + offset[i] * factor for i in range(3)))


def set_target_distance(node, distance):
    """Like Max: move the target on the sight line, leaving the camera still."""
    distance = float(distance)
    if not _is_finite(distance) or distance <= 1e-5:
        raise ValueError("目标距离必须大于 0.00001。")
    info = rig_info(node)
    camera = _world_position(info["camera"])
    direction = _unit(_sub(_world_position(info["target"]), camera))
    with _undo("Set Target Camera Distance"):
        cmds.xform(info["target"], worldSpace=True,
                   translation=tuple(camera[i] + distance * direction[i] for i in range(3)))


def _angle_radians(angle):
    angle = float(angle)
    if not _is_finite(angle):
        raise ValueError("旋转角度必须是有限数值。")
    return angle if cmds.currentUnit(query=True, angle=True) == "rad" else math.radians(angle)


def _rotated_vector(vector, axis, angle):
    axis = _unit(axis)
    cosine, sine = math.cos(angle), math.sin(angle)
    cross = _cross(axis, vector)
    dot = sum(a*b for a, b in zip(axis, vector))
    return tuple(vector[i]*cosine + cross[i]*sine + axis[i]*dot*(1-cosine)
                 for i in range(3))


def pan_camera(node, yaw=0.0, pitch=0.0):
    """Pan/tilt about the camera, by moving its target at constant distance."""
    yaw, pitch = _angle_radians(yaw), _angle_radians(pitch)
    info = rig_info(node)
    matrix = cmds.xform(info["camera"], query=True, worldSpace=True, matrix=True)
    camera = _world_position(info["camera"])
    offset = _sub(_world_position(info["target"]), camera)
    right = _unit(tuple(matrix[i] for i in (0, 1, 2)))
    up = _unit(tuple(matrix[i] for i in (4, 5, 6)))
    offset = _rotated_vector(offset, up, yaw)
    right = _rotated_vector(right, up, yaw)
    offset = _rotated_vector(offset, right, pitch)
    with _undo("Pan Target Camera"):
        cmds.xform(info["target"], worldSpace=True,
                   translation=tuple(camera[i] + offset[i] for i in range(3)))


def orbit_camera(node, yaw=0.0, pitch=0.0):
    """Orbit the camera around its fixed target, preserving target distance."""
    yaw, pitch = _angle_radians(yaw), _angle_radians(pitch)
    info = rig_info(node)
    matrix = cmds.xform(info["camera"], query=True, worldSpace=True, matrix=True)
    target = _world_position(info["target"])
    offset = _sub(_world_position(info["camera"]), target)
    right = _unit(tuple(matrix[i] for i in (0, 1, 2)))
    up = _unit(tuple(matrix[i] for i in (4, 5, 6)))
    offset = _rotated_vector(offset, up, yaw)
    right = _rotated_vector(right, up, yaw)
    offset = _rotated_vector(offset, right, pitch)
    with _undo("Orbit Target Camera"):
        cmds.xform(info["camera"], worldSpace=True,
                   translation=tuple(target[i] + offset[i] for i in range(3)))


def parameters(node):
    info = rig_info(node)
    return {"lens": cmds.getAttr(info["shape"] + ".focalLength"),
            "roll": cmds.getAttr(info["camera"] + ".roll"),
            "distance": _length(_sub(_world_position(info["target"]),
                                      _world_position(info["camera"]))),
            "targetSize": (cmds.getAttr(info["camera"] + ".targetSize")
                           if cmds.attributeQuery("targetSize", node=info["camera"], exists=True)
                           else 1.0),
            "iconScale": cmds.getAttr(info["shape"] + ".locatorScale"),
            "version": cmds.getAttr(info["root"] + "." + TAG)}


def set_parameter(node, parameter, value):
    info = rig_info(node)
    value = float(value)
    if not _is_finite(value):
        raise ValueError("参数必须是有限数值。")
    if parameter == "distance":
        return set_target_distance(node, value)
    if parameter not in ("lens", "roll", "targetSize", "iconScale"):
        raise ValueError("未知相机参数：" + _text(parameter))
    if parameter in ("lens", "targetSize", "iconScale") and value <= 0:
        raise ValueError("焦距和显示大小必须大于零。")
    if parameter in ("targetSize", "iconScale") and not cmds.attributeQuery(
            parameter, node=info["camera"], exists=True):
        raise ValueError("这是旧版相机，请先点“升级当前旧版相机”。")
    with _undo("Set Target Camera Parameter"):
        cmds.setAttr(info["camera"] + "." + parameter, value)


def upgrade_rig(node):
    """Explicit, undoable conversion of an unmodified v1 rig, retaining anim curves.

    Do not silently modify saved rigs when loading the new module. Nonstandard
    connections/pivots are rejected rather than guessing or discarding user work.
    """
    info = rig_info(node)
    root, camera, target = info["root"], info["camera"], info["target"]
    version = cmds.getAttr(root + "." + TAG)
    if version == VERSION:
        return info
    if version == "1.3.0":
        with _undo("Upgrade Max Target Camera"):
            _ensure_horizon_control(info, False)
            cmds.setAttr(root + "." + TAG, lock=False)
            cmds.setAttr(root + "." + TAG, VERSION, type="string", lock=True)
        return rig_info(root)
    if version not in ("1.0.0", "1.1.0", "1.2.0", "1.2.1"):
        raise ValueError("暂不自动升级这个版本：" + _text(version))
    if any(cmds.referenceQuery(n, isNodeReferenced=True) for n in
           (root, camera, target, info["up"])):
        raise ValueError("请在引用相机的源文件中升级。")
    if cmds.getAttr(camera + ".rotateOrder") != 0:
        raise ValueError("旧相机的旋转顺序已被改动，保留原状；请另建新版相机。")
    for attr in ("rotateAxis", "rotatePivot", "rotatePivotTranslate"):
        if any(abs(x) > 1e-10 for x in cmds.getAttr(camera + "." + attr)[0]):
            raise ValueError("旧相机的轴/枢轴有自定义修改，不能安全自动升级。")
    for part in (camera, target, info["up"]):
        if (cmds.listRelatives(part, parent=True, fullPath=True) or []) != [root]:
            raise ValueError("旧相机层级被调整过，不能安全自动升级。")
    # A compound query does not necessarily return connections made to its
    # children (as in saved v1.2.1 rigs). Inspect the exact child plugs too.
    pairs = []
    for attr in ("rotate", "rotateX", "rotateY", "rotateZ"):
        found = cmds.listConnections(camera + "." + attr, source=True, destination=False,
                                      connections=True, plugs=True) or []
        for index in range(0, len(found), 2):
            pair = (found[index], found[index + 1])
            if pair not in pairs:
                pairs.append(pair)
    inputs = [plug for pair in pairs for plug in pair]
    constraints = list(set(source.split(".")[0] for destination, source in pairs
                           if cmds.nodeType(source.split(".")[0]) == "aimConstraint"))
    utilities = cmds.listConnections(root + ".mtcUtilities", source=True, destination=False) or []
    if len(constraints) != 1 or _long(constraints[0]) not in [_long(n) for n in utilities]:
        raise ValueError("旧相机约束不是标准工具结构，保留原状。")
    old_aim = _long(constraints[0])
    actual_targets = cmds.aimConstraint(old_aim, query=True, targetList=True) or []
    if [_long(n) for n in actual_targets] != [target]:
        raise ValueError("目标约束有额外目标或自定义接线，保留原状。")
    aliases = cmds.aimConstraint(old_aim, query=True, weightAliasList=True) or []
    if (len(aliases) != 1 or abs(cmds.getAttr(old_aim + "." + aliases[0]) - 1.0) > 1e-10 or
            cmds.listConnections(old_aim + "." + aliases[0], source=True, destination=False)):
        raise ValueError("目标权重被调整或动画化，不能自动升级。")
    for attr, expected in (("aimVector", (0, 0, -1)), ("upVector", (0, 1, 0)),
                            ("worldUpVector", (0, 1, 0))):
        if (tuple(cmds.getAttr(old_aim + "." + attr)[0]) != expected or
                cmds.listConnections(old_aim + "." + attr, source=True, destination=False)):
            raise ValueError("目标约束方向已被改动，保留原状。")
    up_source = cmds.listConnections(old_aim + ".worldUpMatrix", source=True, destination=False) or []
    if (cmds.getAttr(old_aim + ".worldUpType") != 2 or len(up_source) != 1 or
            _long(up_source[0]) != info["up"]):
        raise ValueError("上方向约束已被改动，保留原状。")
    for attr in ("rotateAxis", "rotateOrder", "rotatePivot", "rotatePivotTranslate"):
        if cmds.listConnections(camera + "." + attr, source=True, destination=False):
            raise ValueError("旧相机的旋转轴或枢轴被外部驱动，保留原状。")
    for index in range(0, len(inputs), 2):
        if _long(inputs[index + 1].split(".")[0]) != old_aim:
            raise ValueError("存在外部旋转连接，不能安全自动升级。")
    for attr in ("offsetX", "offsetY"):
        if (abs(cmds.getAttr(old_aim + "." + attr)) > 1e-10 or
                cmds.listConnections(old_aim + "." + attr, source=True, destination=False)):
            raise ValueError("旧相机的目标偏移有自定义修改，保留原状。")
    for name, destination in (("roll", old_aim + ".offsetZ"),
                              ("lens", info["shape"] + ".focalLength")):
        if not cmds.isConnected(camera + "." + name, destination):
            raise ValueError("旧相机的 {} 接线被改动过，保留原状。".format(name))
        outgoing = cmds.listConnections(camera + "." + name, source=False,
                                         destination=True, plugs=True) or []
        for plug in outgoing:
            same_node = _long(plug.split(".")[0]) == _long(destination.split(".")[0])
            if not same_node or plug.split(".", 1)[1] != destination.split(".", 1)[1]:
                raise ValueError("旧参数驱动了其他对象，不能安全自动升级。")
    target_shapes = cmds.listRelatives(target, shapes=True, noIntermediate=True, fullPath=True) or []
    if (len(target_shapes) != 1 or cmds.nodeType(target_shapes[0]) != "nurbsCurve" or
            cmds.listConnections(target_shapes[0] + ".create", source=True, destination=False)):
        raise ValueError("目标外形有自定义历史，保留原状。")
    values = {name: cmds.getAttr(camera + "." + name) for name in ("roll", "lens")}
    sources = {name: (cmds.listConnections(camera + "." + name, source=True,
                                          destination=False, plugs=True) or [])
               for name in ("roll", "lens")}
    pose = cmds.xform(camera, query=True, worldSpace=True, matrix=True)
    stem = root.rsplit("|", 1)[-1].rsplit("_RIG", 1)[0]
    label = "Upgrade Max Target Camera"
    cmds.undoInfo(openChunk=True, chunkName=label)
    try:
        for attr in ("rx", "ry", "rz", "rotateOrder", "rotateAxisX", "rotateAxisY", "rotateAxisZ"):
            cmds.setAttr(camera + "." + attr, lock=False)
        for index in range(0, len(inputs), 2):
            cmds.disconnectAttr(inputs[index + 1], inputs[index])
        cmds.disconnectAttr(camera + ".roll", old_aim + ".offsetZ")
        cmds.disconnectAttr(camera + ".lens", info["shape"] + ".focalLength")
        created = []
        new_utilities = _aim_with_editable_roll(root, camera, target, info["up"], stem, created)
        for name, destination in (("roll", camera + ".rotateZ"),
                                  ("lens", info["shape"] + ".focalLength")):
            cmds.setAttr(destination, values[name])
            for source in sources[name]:
                cmds.disconnectAttr(source, camera + "." + name)
                cmds.connectAttr(source, destination)
            cmds.deleteAttr(camera + "." + name)
            _proxy(camera, name, destination, "Roll" if name == "roll" else "Lens (mm)")
        _proxy(camera, "iconScale", info["shape"] + ".locatorScale", "Camera Icon Scale")
        cmds.scale(0.3, 0.3, 0.3, target + ".cv[*]", relative=True, objectSpace=True)
        new_utilities.extend(_target_display(target, camera, stem, created))
        _color(target, (0.35, 1.0, 0.4), 14)
        for attr in ("rx", "ry", "rz", "sx", "sy", "sz"):
            cmds.setAttr(target + "." + attr, lock=False, keyable=True)
        indices = cmds.getAttr(root + ".mtcUtilities", multiIndices=True) or []
        first = max(indices + [-1]) + 1
        for index, utility in enumerate(new_utilities):
            _link(root, utility, index=first + index)
        cmds.delete(old_aim)
        cmds.setAttr(root + ".displayHandle", False)
        cmds.setAttr(root + "." + TAG, lock=False)
        cmds.setAttr(root + "." + TAG, VERSION, type="string", lock=True)
        actual = cmds.xform(camera, query=True, worldSpace=True, matrix=True)
        if max(abs(a-b) for a, b in zip(pose, actual)) > 1e-5:
            raise RuntimeError("升级后的取景与原相机不一致，已取消升级。")
    except Exception:
        cmds.undoInfo(closeChunk=True)
        # Never undo an unrelated earlier user operation if the first edit failed.
        if cmds.undoInfo(query=True, undoName=True) == label:
            cmds.undo()
        raise
    else:
        cmds.undoInfo(closeChunk=True)
    return rig_info(root)


def key_controls(node):
    info = rig_info(node)
    with _undo("Key Target Camera Controls"):
        cmds.setKeyframe(info["camera"], attribute=["tx", "ty", "tz", "roll", "lens"])
        cmds.setKeyframe(info["target"], attribute=["tx", "ty", "tz"])
        cmds.setKeyframe(info["root"], attribute=["tx", "ty", "tz", "rx", "ry", "rz"])
        cmds.setKeyframe(info["up"], attribute=["rx", "ry", "rz"])


def delete_rig(node):
    root = resolve_rig(node)
    if cmds.referenceQuery(root, isNodeReferenced=True):
        raise ValueError("不能删除引用文件中的相机组，请在源文件中编辑。")
    utilities = cmds.listConnections(root + ".mtcUtilities", source=True, destination=False) or []
    with _undo("Delete Max Target Camera"):
        # Constraints live under the camera; delete DG helpers first and root last.
        for utility in set(utilities):
            if cmds.objExists(utility):
                cmds.delete(utility)
        cmds.delete(root)


def _model_panel():
    global _last_panel
    panels = cmds.getPanel(type="modelPanel") or []
    focus = cmds.getPanel(withFocus=True)
    if focus in panels:
        _last_panel = focus
        return focus
    visible = set(cmds.getPanel(visiblePanels=True) or [])
    for panel in panels:
        if panel in visible and cmds.modelEditor(panel, query=True, activeView=True):
            _last_panel = panel
            return panel
    if _last_panel in panels and _last_panel in visible:
        return _last_panel
    for panel in panels:
        if panel in visible:
            _last_panel = panel
            return panel
    raise ValueError("没有可用的三维视口，请打开一个透视视口。")


def _view_layout(panel=None):
    """Read a stable viewing plane; never move the user's viewport camera."""
    panel = panel or _model_panel()
    source = cmds.modelPanel(panel, query=True, camera=True)
    transform, shape = _camera_parts(source)
    matrix = cmds.xform(transform, query=True, worldSpace=True, matrix=True)
    right = _unit(tuple(matrix[i] for i in (0, 1, 2)))
    up = _unit(tuple(matrix[i] for i in (4, 5, 6)))
    forward = _unit(tuple(-matrix[i] for i in (8, 9, 10)))
    eye = _world_position(transform)
    depth = max(float(cmds.getAttr(shape + ".centerOfInterest")),
                float(cmds.getAttr(shape + ".nearClipPlane")) * 4.0, 0.01)
    center = tuple(eye[i] + forward[i] * depth for i in range(3))
    # The native model-editor control is available without a Qt binding or
    # M3dView call during application startup.
    control = cmds.modelPanel(panel, query=True, control=True)
    width = max(1, cmds.control(control, query=True, width=True))
    height = max(1, cmds.control(control, query=True, height=True))
    aspect = float(width) / height
    if cmds.getAttr(shape + ".orthographic"):
        half_width = float(cmds.getAttr(shape + ".orthographicWidth")) * 0.5
        half_height = half_width / aspect
        lens = 35.0
    else:
        lens = float(cmds.getAttr(shape + ".focalLength"))
        horizontal = float(cmds.getAttr(shape + ".horizontalFilmAperture")) * 25.4
        vertical = float(cmds.getAttr(shape + ".verticalFilmAperture")) * 25.4
        half_width, half_height = depth * horizontal / (2*lens), depth * vertical / (2*lens)
        fit = int(cmds.getAttr(shape + ".filmFit"))
        use_horizontal = fit == 1 or (fit == 0 and aspect >= horizontal/vertical) or (
            fit == 3 and aspect < horizontal/vertical)
        if use_horizontal:
            half_height = half_width / aspect
        else:
            half_width = half_height * aspect
        scale = float(cmds.getAttr(shape + ".overscan"))
        half_width *= scale
        half_height *= scale
    return {"panel": panel, "source": transform, "shape": shape, "right": right, "up": up,
            "forward": forward, "center": center, "depth": depth, "eye": eye,
            "orthographic": bool(cmds.getAttr(shape + ".orthographic")),
            "half_width": half_width, "half_height": half_height,
            "width": width, "height": height, "lens": lens}


def create_near_view(name="MaxTarget", panel=None, target_position=None):
    """Place BOTH controls inside the view, rather than at the viewing eye."""
    layout = _view_layout(panel)
    span = max(min(layout["half_width"], layout["half_height"]) * 0.65, 0.001)
    target = _v3(target_position) if target_position is not None else tuple(
        layout["center"][i] + layout["right"][i]*span*0.5 for i in range(3))
    camera = tuple(target[i] - layout["right"][i]*span + layout["up"][i]*span*0.10
                   for i in range(3))
    return create_camera(name=name, camera_position=camera, target_position=target,
                          focal_length=layout["lens"], keep_horizon=True)


def _draw_world_point(layout, raw_point):
    """Maya's viewPlane points lie on the near clip plane, not the focus plane.

    Push the native pointer ray out to the current view focus so the new
    camera is visible in front of the viewer instead of sitting at its eye.
    """
    point = _v3(raw_point)
    normal = layout["forward"]
    if layout["orthographic"]:
        offset = sum(a*b for a, b in zip(_sub(layout["center"], point), normal))
        return tuple(point[i] + normal[i]*offset for i in range(3))
    ray = _sub(point, layout["eye"])
    along = sum(a*b for a, b in zip(ray, normal))
    if along <= 1e-10:
        raise ValueError("鼠标投影不在当前视口前方，请重新启动创建工具。")
    factor = layout["depth"] / along
    return _v3(tuple(layout["eye"][i] + ray[i]*factor for i in range(3)))


class _DrawCamera(object):
    """Press anchors the target; drag positions the camera. No saved callbacks."""
    def __init__(self, name):
        self.name = name
        self.info = None
        self.anchor = None
        self.layout = None
        self.previous_selection = []
        self.finished = False
        self.preview_distance = None
        self.button = 0

    def initialize(self, *unused):
        cmds.inViewMessage(amg="max目标相机：按下定目标 → 拖动定机位 → 松开完成；Q 退出。",
                           pos="midCenter", fade=True)

    def press(self, *unused):
        self.info, self.anchor, self.finished = None, None, False
        self.button = cmds.draggerContext(DRAW_CONTEXT, query=True, button=True)
        if self.button != 1:
            return
        panel = cmds.getPanel(underPointer=True)
        if panel not in (cmds.getPanel(type="modelPanel") or []):
            panel = _model_panel()
        self.layout = _view_layout(panel)
        self.previous_selection = cmds.ls(selection=True, long=True) or []
        self.anchor = _draw_world_point(self.layout, cmds.draggerContext(
            DRAW_CONTEXT, query=True, anchorPoint=True))
        self.preview_distance = None

    def drag(self, *unused):
        if self.anchor is None or self.button != 1:
            return
        try:
            # The press position is the fixed target; only the camera follows
            # the pointer, including every preview update after initial creation.
            camera = _draw_world_point(self.layout, cmds.draggerContext(
                DRAW_CONTEXT, query=True, dragPoint=True))
            distance = _length(_sub(camera, self.anchor))
            # A zero-length click must not create a broken aim constraint.
            if distance < max(min(self.layout["half_width"], self.layout["half_height"])*0.003, 1e-5):
                return
            if self.info is None:
                self.info = create_camera(name=self.name, camera_position=camera,
                                          target_position=self.anchor, focal_length=self.layout["lens"],
                                          keep_horizon=True)
                self.preview_distance = distance
            else:
                cmds.xform(self.info["camera"], worldSpace=True, translation=camera)
                # Resize the two preview icons with the actual drawn separation.
                cmds.setAttr(self.info["camera"] + ".targetSize", distance/self.preview_distance)
                cmds.setAttr(self.info["shape"] + ".locatorScale", max(distance*0.008, 0.0001))
            cmds.draggerContext(DRAW_CONTEXT, edit=True, drawString="目标 → 机位")
            cmds.refresh(currentView=True)
        except Exception as error:
            cmds.warning("[max目标相机] 拖动创建失败：" + _text(error))
            self.cancel()

    def release(self, *unused):
        if self.button != 1:
            return
        if self.info is not None:
            self.finished = True
            cmds.select(self.info["camera"], replace=True)
            if _ui is not None and cmds.window(WINDOW, exists=True):
                _ui.refresh(self.info["root"])
        else:
            cmds.warning("请按住左键拖出一段距离；单击不会创建相机。")
        self.anchor = None
        # Defer tool switching until Maya closes the dragger's undo chunk.
        import maya.utils as utils
        utils.executeDeferred(self.exit)

    def exit(self):
        if cmds.currentCtx() == DRAW_CONTEXT:
            cmds.setToolTo("moveSuperContext")

    def cancel(self, *unused):
        if not self.finished and self.info is not None and cmds.objExists(self.info["root"]):
            delete_rig(self.info["root"])
            existing = [n for n in self.previous_selection if cmds.objExists(n)]
            cmds.select(existing, replace=True) if existing else cmds.select(clear=True)
        self.info, self.anchor = None, None


def start_interactive(name="MaxTarget"):
    global _draw_tool
    if cmds.about(batch=True):
        raise RuntimeError("鼠标拖动创建需要 Maya 三维视口。")
    _preflight()
    _model_panel()
    if cmds.draggerContext(DRAW_CONTEXT, exists=True):
        if cmds.currentCtx() == DRAW_CONTEXT:
            cmds.setToolTo("selectSuperContext")
        cmds.deleteUI(DRAW_CONTEXT)
    _draw_tool = _DrawCamera(name)
    cmds.draggerContext(DRAW_CONTEXT, cursor="crossHair", space="world",
                        projection="viewPlane", undoMode="step", stepsCount=1,
                        initialize=_draw_tool.initialize, pressCommand=_draw_tool.press,
                        dragCommand=_draw_tool.drag, releaseCommand=_draw_tool.release,
                        finalize=_draw_tool.cancel,
                        helpString="按下定目标，拖出相机，松开完成；Esc / Q 退出。")
    cmds.setToolTo(DRAW_CONTEXT)
    return DRAW_CONTEXT


class _ToolUI(object):
    def __init__(self):
        self.uuids = []
        self.parameter_fields = {}
        self.reading_parameters = False
        if cmds.window(WINDOW, exists=True):
            cmds.deleteUI(WINDOW)
        self.window = cmds.window(WINDOW, title="max目标相机 v{}".format(VERSION),
                                   sizeable=True, widthHeight=(390, 630))
        cmds.scrollLayout(childResizable=True)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=5, columnAttach=("both", 8))
        cmds.text(label="默认无翻滚；W 只移动，E 本地 Z / Roll 才添加滚转。", align="left", height=24)
        self.name = cmds.textFieldGrp(label="名称", text="MaxTarget", columnWidth2=(55, 290))
        self.use_selection = cmds.checkBox(label="目标放到所选物体中心", value=False)
        cmds.button(label="鼠标拖动创建：按下目标 → 拖出相机", height=32,
                    command=self.callback(self.draw))
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(181, 181))
        cmds.button(label="视野内创建（近距离）", height=30, command=self.callback(self.create, False))
        cmds.button(label="复制视口机位", height=30, command=self.callback(self.create, True))
        cmds.setParent("..")
        self.menu = cmds.optionMenu(label="相机", width=360,
                                    changeCommand=self.callback(self.read_parameters))
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(181, 181))
        cmds.button(label="刷新列表 / 参数", command=self.callback(self.refresh))
        cmds.button(label="识别所选相机 / 目标", command=self.callback(self.from_selection))
        cmds.setParent("..")
        cmds.frameLayout(label="镜头与显示参数（可直接调整）", collapsable=False, marginWidth=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=3)
        unit = cmds.currentUnit(query=True, linear=True)
        angle = cmds.currentUnit(query=True, angle=True)
        for key, label, value in (("lens", "焦距（mm）", 35),
                                   ("roll", "滚转（{}）".format(angle), 0),
                                   ("distance", "目标距离（{}）".format(unit), 10),
                                   ("targetSize", "目标框缩放", 1),
                                   ("iconScale", "相机图标缩放", 1)):
            self.parameter_fields[key] = cmds.floatFieldGrp(
                label=label, numberOfFields=1, value1=value, precision=4,
                columnWidth2=(130, 190), changeCommand=self.callback(self.edit_parameter, key))
        cmds.setParent(".."); cmds.setParent("..")
        for left, right in ((("选机位 / W 移动", "camera"), ("选目标 / W 移动", "target")),
                            (("选整体 / E 环绕", "root"), ("手动 UP（取消水平锁）", "up"))):
            cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(181, 181))
            for label, part in (left, right):
                cmds.button(label=label, height=26, command=self.callback(self.apply, select_part, part))
            cmds.setParent("..")
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(181, 181))
        cmds.button(label="从相机观看", command=self.callback(self.look))
        cmds.button(label="给控制器打关键帧", command=self.callback(self.apply, key_controls))
        cmds.setParent("..")
        cmds.button(label="修复移动翻滚 / 回正（保留滚转关键帧）",
                    command=self.callback(self.relevel))
        cmds.button(label="升级当前旧版相机（保留动画 / 可撤销）",
                    command=self.callback(self.upgrade))
        cmds.frameLayout(label="推拉、摇摄与其他操作", collapsable=True, collapse=True, marginWidth=5)
        cmds.columnLayout(adjustableColumn=True, rowSpacing=4)
        cmds.rowLayout(numberOfColumns=2, adjustableColumn=1, columnWidth2=(176, 176))
        cmds.button(label="推近 10%", command=self.callback(self.apply, dolly, 0.9))
        cmds.button(label="拉远 10%", command=self.callback(self.apply, dolly, 1.1))
        cmds.setParent("..")
        for label, fn in (("原地摇摄", pan_camera), ("绕目标环绕", orbit_camera)):
            cmds.text(label=label + "（每步 5°）", align="left")
            cmds.rowLayout(numberOfColumns=4, adjustableColumn=1, columnWidth4=(87, 87, 87, 87))
            for caption, yaw, pitch in (("左", 5, 0), ("右", -5, 0), ("上", 0, 5), ("下", 0, -5)):
                cmds.button(label=caption, command=self.callback(self.navigate, fn, yaw, pitch))
            cmds.setParent("..")
        cmds.button(label="检查兼容性", command=self.callback(self.show_compatibility))
        cmds.button(label="删除这套工具相机…", command=self.callback(self.remove))
        cmds.setParent(".."); cmds.setParent("..")
        cmds.text(label="X/Y 朝向由目标计算，不是自由相机。\n"
                        "通道盒 Target Distance 是实测值，改距离请用上面的输入框。\n"
                        "俯仰接近 UP 时仍需调整上方向，避免极点翻转。", align="left", height=53)
        self.status = cmds.text(label="就绪。参数框点击“刷新”读取当前值。", align="left", height=26)
        self.refresh()
        cmds.showWindow(self.window)

    def read_parameters(self):
        if not self.parameter_fields or not self.uuids:
            return
        values = parameters(self.active())
        info = rig_info(self.active())
        self.reading_parameters = True
        try:
            for key, control in self.parameter_fields.items():
                editable = key not in ("targetSize", "iconScale") or cmds.attributeQuery(
                    key, node=info["camera"], exists=True)
                cmds.floatFieldGrp(control, edit=True, value1=values[key], enable=editable)
        finally:
            self.reading_parameters = False

    def edit_parameter(self, key):
        if not self.reading_parameters:
            value = cmds.floatFieldGrp(self.parameter_fields[key], query=True, value1=True)
            set_parameter(self.active(), key, value)
            self.read_parameters()

    def upgrade(self):
        info = upgrade_rig(self.active())
        self.refresh(info["root"])
        return info

    def navigate(self, fn, yaw, pitch):
        if cmds.currentUnit(query=True, angle=True) == "rad":
            yaw, pitch = math.radians(yaw), math.radians(pitch)
        fn(self.active(), yaw, pitch)
        self.read_parameters()

    def callback(self, fn, *args):
        # Capture arguments now; no Python-3-only keyword-only lambda parameters.
        def invoke(*maya_event_args):
            return self.run(fn, *args)
        return invoke

    def show_compatibility(self):
        report = compatibility_report()
        message = ("Maya {maya_version} / Python {python_version}\n"
                   "工具版本：{tool_version}；不依赖 PySide 或 OpenMaya Python API。\n").format(**report)
        message += ("必要节点检查：通过。\n" if report["capability_check_passed"] else
                    "缺少必要节点：" + ", ".join(report["missing_node_types"]) + "\n")
        if not report["in_target_range"]:
            message += "此 Maya 年份不在当前兼容目标内。\n"
        message += report["note"]
        cmds.confirmDialog(title="跨版本环境自检", message=message, button=["确定"])
        return report

    def run(self, fn, *args):
        try:
            result = fn(*args)
            cmds.text(self.status, edit=True, label="完成。Ctrl+Z 可撤销场景修改。")
            return result
        except Exception as error:
            cmds.warning("[Max Target Camera] " + _text(error))
            cmds.text(self.status, edit=True, label=_text(error))
            return None

    def apply(self, fn, *args):
        return fn(self.active(), *args)

    def refresh(self, preferred=None):
        for item in cmds.optionMenu(self.menu, query=True, itemListLong=True) or []:
            cmds.deleteUI(item)
        roots = list_rigs()
        self.uuids = [cmds.ls(root, uuid=True)[0] for root in roots]
        if not roots:
            cmds.menuItem(parent=self.menu, label="（请先创建目标摄像机）")
            return
        for root in roots:
            cmds.menuItem(parent=self.menu, label=root.rsplit("|", 1)[-1])
        if preferred:
            root_id = cmds.ls(resolve_rig(preferred), uuid=True)[0]
            if root_id in self.uuids:
                cmds.optionMenu(self.menu, edit=True, select=self.uuids.index(root_id) + 1)
        self.read_parameters()

    def active(self):
        index = cmds.optionMenu(self.menu, query=True, select=True) - 1
        if index < 0 or index >= len(self.uuids):
            raise ValueError("请先创建目标摄像机。")
        found = cmds.ls(self.uuids[index], long=True) or []
        if len(found) != 1:
            raise ValueError("相机已被删除，请刷新列表。")
        return found[0]

    def from_selection(self):
        selection = cmds.ls(selection=True, long=True) or []
        if not selection:
            raise ValueError("请选中一台工具相机或它的控制器。")
        self.refresh(resolve_rig(selection[0]))

    def draw(self):
        return start_interactive(cmds.textFieldGrp(self.name, query=True, text=True))

    def relevel(self):
        result = level_horizon(self.active(), reset_unkeyed_roll=True)
        self.read_parameters()
        return result

    def create(self, from_view):
        target = selection_center() if cmds.checkBox(self.use_selection, query=True, value=True) else None
        name = cmds.textFieldGrp(self.name, query=True, text=True)
        if from_view:
            source = cmds.modelPanel(_model_panel(), query=True, camera=True)
            info = create_camera(name=name, target_position=target, source_camera=source)
        else:
            info = create_near_view(name=name, target_position=target)
        self.refresh(info["root"])

    def look(self):
        cmds.lookThru(_model_panel(), rig_info(self.active())["camera"])

    def remove(self):
        root = self.active()
        answer = cmds.confirmDialog(title="删除目标摄像机", message="删除整个 {} 层级及工具辅助节点？\n后来放进这组的子物体也会删除；可以撤销。".format(root),
                                    button=["删除", "取消"], defaultButton="取消", cancelButton="取消",
                                    dismissString="取消")
        if answer == "删除":
            delete_rig(root)
            self.refresh()


def show():
    global _ui
    if cmds.about(batch=True):
        raise RuntimeError("窗口只能在 Maya 界面中打开；批处理请直接调用 create_camera()。")
    _preflight()
    _model_panel()
    _ui = _ToolUI()
    return _ui


def onMayaDroppedPythonFile(*args):
    show()
    return True


if __name__ == "__main__":
    show()
