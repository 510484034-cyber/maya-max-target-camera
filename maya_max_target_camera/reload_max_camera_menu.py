# -*- coding: utf-8 -*-
"""Fresh entry point for repairing a session that cached the original loader."""
from __future__ import absolute_import, division, print_function, unicode_literals
import os


def onMayaDroppedPythonFile(*unused):
    path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "load_menu_now.py")
    namespace={"__file__":path,"__name__":"max_camera_fresh_loader"}
    with open(path,"rb") as stream:
        code=compile(stream.read(),path,"exec")
    exec(code,namespace)
    namespace["load"]()
    return True


if __name__=="__main__":
    onMayaDroppedPythonFile()
