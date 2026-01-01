"""Re-export view widgets for convenient imports.

This module exposes the main view classes so other modules can import
from `view` instead of referencing submodules directly.
"""
from .main_window import MainWindow
from .sync_progress_dialog import SyncProgressDialog

__all__ = ["MainWindow", "SyncProgressDialog"]
