from __future__ import annotations

import ctypes
from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtCore, QtWidgets
import qtmax

HERE = Path(__file__).resolve().parent
DLL_PATH = HERE / "AlokViewportIsolate.dll"
_WINDOW = None
_DLL = None

ERROR_TEXT = {
    -1: "Invalid viewport/selection data.",
    -2: "3ds Max node display control is unavailable.",
    -4: "3ds Max refused to activate the viewport display callback.",
}


def _load_dll():
    global _DLL
    if _DLL is not None:
        return _DLL

    if not DLL_PATH.exists():
        raise FileNotFoundError(
            "AlokViewportIsolate.dll is missing.\n\n"
            "Keep the compiled DLL beside this Python file."
        )

    dll = ctypes.WinDLL(str(DLL_PATH))
    dll.AlokVP_Isolate.argtypes = [
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.c_int,
    ]
    dll.AlokVP_Isolate.restype = ctypes.c_int
    dll.AlokVP_Restore.argtypes = []
    dll.AlokVP_Restore.restype = ctypes.c_int
    dll.AlokVP_IsActive.argtypes = []
    dll.AlokVP_IsActive.restype = ctypes.c_int
    dll.AlokVP_TargetViewID.argtypes = []
    dll.AlokVP_TargetViewID.restype = ctypes.c_int
    dll.AlokVP_ExCallCount.argtypes = []
    dll.AlokVP_ExCallCount.restype = ctypes.c_uint64
    dll.AlokVP_LegacyCallCount.argtypes = []
    dll.AlokVP_LegacyCallCount.restype = ctypes.c_uint64
    dll.AlokVP_SuppressedCount.argtypes = []
    dll.AlokVP_SuppressedCount.restype = ctypes.c_uint64
    dll.AlokVP_LastSeenViewID.argtypes = []
    dll.AlokVP_LastSeenViewID.restype = ctypes.c_int
    dll.AlokVP_HasPreviousCallback.argtypes = []
    dll.AlokVP_HasPreviousCallback.restype = ctypes.c_int
    _DLL = dll
    return dll


def _selected_handles():
    handles = []
    seen = set()
    for node in list(rt.selection):
        try:
            handle = int(rt.GetHandleByAnim(node))
        except Exception:
            continue
        if handle not in seen:
            seen.add(handle)
            handles.append(handle)
    return handles


def _force_redraw():
    try:
        rt.completeRedraw()
    except Exception:
        rt.redrawViews()


def isolate_active_viewport():
    handles = _selected_handles()
    if not handles:
        raise RuntimeError("Select the object(s) you want to keep visible first.")

    view_id = int(rt.viewport.activeViewportID)
    array_type = ctypes.c_uint64 * len(handles)
    handle_array = array_type(*handles)

    result = _load_dll().AlokVP_Isolate(view_id, handle_array, len(handles))
    if result != 1:
        raise RuntimeError(ERROR_TEXT.get(result, f"Native bridge error: {result}"))

    _force_redraw()
    return view_id, len(handles)


def restore_viewport():
    result = _load_dll().AlokVP_Restore()
    if result != 1:
        raise RuntimeError(f"Native bridge error: {result}")
    _force_redraw()


def diagnostics():
    dll = _load_dll()
    return {
        "ex": int(dll.AlokVP_ExCallCount()),
        "legacy": int(dll.AlokVP_LegacyCallCount()),
        "suppressed": int(dll.AlokVP_SuppressedCount()),
        "seen_view": int(dll.AlokVP_LastSeenViewID()),
        "target_view": int(dll.AlokVP_TargetViewID()),
        "chained": bool(dll.AlokVP_HasPreviousCallback()),
    }


class ViewportIsolatePalette(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("VP ISOLATE")
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setFixedWidth(270)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.setSpacing(7)

        self.isolate_btn = QtWidgets.QPushButton("ISOLATE THIS VIEWPORT")
        self.isolate_btn.setMinimumHeight(46)
        self.restore_btn = QtWidgets.QPushButton("RESTORE THIS VIEWPORT")
        self.restore_btn.setMinimumHeight(38)

        self.status = QtWidgets.QLabel("Select object(s) → click ISOLATE")
        self.status.setAlignment(QtCore.Qt.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(28)

        self.debug = QtWidgets.QLabel("")
        self.debug.setAlignment(QtCore.Qt.AlignCenter)
        self.debug.setWordWrap(True)
        self.debug.setStyleSheet("font-size: 9px; color: #a0a0a0;")

        safety = QtWidgets.QLabel("VIEWPORT ONLY • RENDERABLE UNTOUCHED")
        safety.setAlignment(QtCore.Qt.AlignCenter)
        safety.setStyleSheet("font-size: 9px; color: #8c8c8c;")

        layout.addWidget(self.isolate_btn)
        layout.addWidget(self.restore_btn)
        layout.addWidget(self.status)
        layout.addWidget(self.debug)
        layout.addWidget(safety)

        self.isolate_btn.clicked.connect(self._on_isolate)
        self.restore_btn.clicked.connect(self._on_restore)
        self.isolate_btn.setStyleSheet(
            "QPushButton { font-weight: 700; font-size: 12px; padding: 7px; }"
        )
        self.restore_btn.setStyleSheet(
            "QPushButton { font-weight: 600; padding: 6px; }"
        )

        self.diag_timer = QtCore.QTimer(self)
        self.diag_timer.setInterval(400)
        self.diag_timer.timeout.connect(self._refresh_diagnostics)

    def showEvent(self, event):
        super().showEvent(event)
        QtCore.QTimer.singleShot(0, self._place_on_east_side)

    def _place_on_east_side(self):
        parent = self.parentWidget()
        if parent is None:
            return
        frame = parent.frameGeometry()
        x = frame.x() + frame.width() - self.width() - 22
        y = frame.y() + 135
        self.move(max(frame.x(), x), max(frame.y(), y))

    def _message_error(self, text):
        self.diag_timer.stop()
        self.status.setText("Not isolated")
        self.debug.setText("")
        QtWidgets.QMessageBox.warning(self, "VP ISOLATE", str(text))

    def _on_isolate(self):
        try:
            view_id, count = isolate_active_viewport()
            self.status.setText(f"Viewport {view_id} • {count} object(s) isolated")
            self.diag_timer.start()
            QtCore.QTimer.singleShot(100, self._refresh_diagnostics)
        except Exception as exc:
            self._message_error(exc)

    def _refresh_diagnostics(self):
        try:
            d = diagnostics()
            chain = " • chained" if d["chained"] else ""
            self.debug.setText(
                f"EX {d['ex']} • hidden {d['suppressed']} • "
                f"seen VP {d['seen_view']} / target {d['target_view']}{chain}"
            )
            if d["ex"] == 0 and d["legacy"] > 0:
                self.status.setText("Legacy callback detected — EX interface not active")
        except Exception:
            pass

    def _on_restore(self):
        try:
            restore_viewport()
            self.diag_timer.stop()
            self.status.setText("Full scene restored")
            self.debug.setText("")
        except Exception as exc:
            self._message_error(exc)

    def closeEvent(self, event):
        self.diag_timer.stop()
        try:
            if _DLL is not None and _DLL.AlokVP_IsActive():
                restore_viewport()
        except Exception:
            pass
        super().closeEvent(event)


def show_palette():
    global _WINDOW
    try:
        if _WINDOW is not None:
            _WINDOW.close()
    except Exception:
        pass

    parent = qtmax.GetQMaxMainWindow()
    _WINDOW = ViewportIsolatePalette(parent)
    _WINDOW.show()
    _WINDOW.raise_()
    _WINDOW.activateWindow()
    return _WINDOW


show_palette()
