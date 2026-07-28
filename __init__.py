# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2025-2026  <Jochen Zeitler>
import importlib.util

if importlib.util.find_spec("FreeCAD") and importlib.util.find_spec("FreeCADGui"):
    from .InitGui import MyWorkbench
else:
    MyWorkbench = None

__all__ = ['MyWorkbench']
