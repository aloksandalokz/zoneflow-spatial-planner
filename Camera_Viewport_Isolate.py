from __future__ import annotations

import ctypes
import math
from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtCore, QtWidgets
import qtmax

HERE = Path(__file__).resolve().parent
DLL_PATH = HERE / "CameraViewportIsolate.dll"
_WINDOW = None
_DLL = None


def is_valid(n):
    try:
        return n is not None and bool(rt.isValidNode(n))
    except Exception:
        return False


def is_camera(n):
    if not is_valid(n):
        return False
    try:
        return str(rt.superClassOf(n)).lower() == "camera"
    except Exception:
        return False


def node_handle(n):
    return int(rt.GetHandleByAnim(n))


def active_or_selected_camera():
    try:
        c = rt.getActiveCamera()
        if is_camera(c):
            return c
    except Exception:
        pass

    cams = [n for n in list(rt.selection) if is_camera(n)]
    if len(cams) == 1:
        return cams[0]
    return None


def descendants(node):
    out = []
    try:
        children = list(node.children)
    except Exception:
        children = []

    for c in children:
        if is_valid(c):
            out.append(c)
            out.extend(descendants(c))
    return out


def expanded_selection():
    """Selection plus descendants, so selecting a group/head keeps its contents."""
    seen = set()
    out = []
    for n in list(rt.selection):
        if not is_valid(n) or is_camera(n):
            continue
        for item in [n] + descendants(n):
            try:
                h = node_handle(item)
            except Exception:
                continue
            if h not in seen:
                seen.add(h)
                out.append(item)
    return out


def bbox(nodes):
    if not nodes:
        raise RuntimeError("Select object(s) first.")

    mn = rt.Point3(1e30, 1e30, 1e30)
    mx = rt.Point3(-1e30, -1e30, -1e30)
    valid_count = 0

    for n in nodes:
        try:
            a, b = n.min, n.max
            mn.x = min(mn.x, a.x)
            mn.y = min(mn.y, a.y)
            mn.z = min(mn.z, a.z)
            mx.x = max(mx.x, b.x)
            mx.y = max(mx.y, b.y)
            mx.z = max(mx.z, b.z)
            valid_count += 1
        except Exception:
            pass

    if valid_count == 0:
        raise RuntimeError("Could not calculate selection bounds.")

    center = (mn + mx) / 2.0
    radius = max(float(rt.length(mx - mn)) * 0.5, 1.0)
    return center, radius


def prop_get(obj, name, default=None):
    try:
        return getattr(obj, name)
    except Exception:
        try:
            return rt.getProperty(obj, rt.Name(name))
        except Exception:
            return default


def prop_set(obj, name, value):
    try:
        setattr(obj, name, value)
        return True
    except Exception:
        try:
            rt.setProperty(obj, rt.Name(name), value)
            return True
        except Exception:
            return False


def load_dll():
    global _DLL
    if _DLL is not None:
        return _DLL

    if not DLL_PATH.exists():
        raise RuntimeError(
            "CameraViewportIsolate.dll is missing. Keep it beside this Python file."
        )

    d = ctypes.WinDLL(str(DLL_PATH))
    d.CameraVP_Isolate.argtypes = [
        ctypes.c_uint64,
        ctypes.POINTER(ctypes.c_uint64),
        ctypes.c_int,
    ]
    d.CameraVP_Isolate.restype = ctypes.c_int
    d.CameraVP_Restore.argtypes = []
    d.CameraVP_Restore.restype = ctypes.c_int
    d.CameraVP_IsActive.argtypes = []
    d.CameraVP_IsActive.restype = ctypes.c_int
    d.CameraVP_TargetCamera.argtypes = []
    d.CameraVP_TargetCamera.restype = ctypes.c_uint64
    d.CameraVP_LastSeenCamera.argtypes = []
    d.CameraVP_LastSeenCamera.restype = ctypes.c_uint64
    d.CameraVP_SuppressedCount.argtypes = []
    d.CameraVP_SuppressedCount.restype = ctypes.c_uint64
    d.CameraVP_ExCallCount.argtypes = []
    d.CameraVP_ExCallCount.restype = ctypes.c_uint64
    _DLL = d
    return d


class Controller:
    def __init__(self):
        self.camera = None
        self.saved_tm = None
        self.saved_target_pos = None
        self.saved_fov = None

    def set_camera(self):
        c = active_or_selected_camera()
        if c is None:
            raise RuntimeError(
                "Activate the camera viewport you want isolated, or select exactly one camera."
            )
        self.camera = c
        self.save_p()
        return c

    def ensure_camera(self):
        if not is_camera(self.camera):
            return self.set_camera()
        return self.camera

    def target_node(self, cam):
        if not bool(prop_get(cam, "targeted", False)):
            return None
        t = prop_get(cam, "target", None)
        return t if is_valid(t) else None

    def isolate(self):
        cam = self.ensure_camera()
        nodes = expanded_selection()
        if not nodes:
            raise RuntimeError("Select the object(s) you want visible in this camera.")

        handles = [node_handle(n) for n in nodes]
        arr_type = ctypes.c_uint64 * len(handles)
        arr = arr_type(*handles)

        code = load_dll().CameraVP_Isolate(
            ctypes.c_uint64(node_handle(cam)), arr, len(handles)
        )
        if code == -2:
            raise RuntimeError("3ds Max node-display control is unavailable.")
        if code == -3:
            raise RuntimeError("3ds Max refused to activate the camera display filter.")
        if code != 1:
            raise RuntimeError(f"Camera isolation error: {code}")

        try:
            rt.completeRedraw()
        except Exception:
            rt.redrawViews()
        return len(nodes)

    def restore(self):
        load_dll().CameraVP_Restore()
        try:
            rt.completeRedraw()
        except Exception:
            rt.redrawViews()

    def diagnostics(self):
        d = load_dll()
        return (
            int(d.CameraVP_ExCallCount()),
            int(d.CameraVP_SuppressedCount()),
            int(d.CameraVP_LastSeenCamera()),
            int(d.CameraVP_TargetCamera()),
        )

    # ------------------------ Camera navigation ------------------------
    def save_p(self):
        cam = self.ensure_camera() if self.camera is None else self.camera
        self.saved_tm = cam.transform
        self.saved_fov = prop_get(cam, "fov", None)
        t = self.target_node(cam)
        self.saved_target_pos = t.pos if t is not None else None

    def restore_p(self):
        cam = self.ensure_camera()
        if self.saved_tm is None:
            raise RuntimeError("No perspective camera pose is saved.")
        t = self.target_node(cam)
        if t is not None and self.saved_target_pos is not None:
            t.pos = self.saved_target_pos
        cam.transform = self.saved_tm
        if self.saved_fov is not None:
            prop_set(cam, "fov", self.saved_fov)
        rt.redrawViews()

    def fit_distance(self, cam, radius):
        try:
            fov = float(prop_get(cam, "fov", 45.0))
        except Exception:
            fov = 45.0
        fov = max(5.0, min(150.0, fov))
        return max(
            radius / max(math.tan(math.radians(fov * 0.5)), 0.05) * 1.35,
            radius * 1.8,
            10.0,
        )

    def axis_pos(self, view, c, d):
        return {
            "TOP": c + rt.Point3(0, 0, d),
            "BOTTOM": c + rt.Point3(0, 0, -d),
            "FRONT": c + rt.Point3(0, -d, 0),
            "BACK": c + rt.Point3(0, d, 0),
            "LEFT": c + rt.Point3(-d, 0, 0),
            "RIGHT": c + rt.Point3(d, 0, 0),
        }[view]

    def free_tm(self, view, c, d):
        p = self.axis_pos(view, c, d)
        rows = {
            "TOP": (rt.Point3(1,0,0), rt.Point3(0,1,0), rt.Point3(0,0,1)),
            "BOTTOM": (rt.Point3(1,0,0), rt.Point3(0,-1,0), rt.Point3(0,0,-1)),
            "FRONT": (rt.Point3(1,0,0), rt.Point3(0,0,1), rt.Point3(0,-1,0)),
            "BACK": (rt.Point3(-1,0,0), rt.Point3(0,0,1), rt.Point3(0,1,0)),
            "LEFT": (rt.Point3(0,-1,0), rt.Point3(0,0,1), rt.Point3(-1,0,0)),
            "RIGHT": (rt.Point3(0,1,0), rt.Point3(0,0,1), rt.Point3(1,0,0)),
        }[view]
        return rt.Matrix3(rows[0], rows[1], rows[2], p)

    def axis(self, view):
        cam = self.ensure_camera()
        nodes = expanded_selection()
        center, radius = bbox(nodes)
        d = self.fit_distance(cam, radius)
        target = self.target_node(cam)

        if target is not None:
            target.pos = center
            cam.pos = self.axis_pos(view, center, d)
            if prop_get(cam, "rollAngle", None) is not None:
                prop_set(cam, "rollAngle", 0.0)
        else:
            cam.transform = self.free_tm(view, center, d)

        rt.redrawViews()
        return len(nodes)

    def fit(self):
        cam = self.ensure_camera()
        nodes = expanded_selection()
        center, radius = bbox(nodes)
        d = self.fit_distance(cam, radius)
        target = self.target_node(cam)

        if target is not None:
            direction = center - cam.pos
            if float(rt.length(direction)) < 1e-6:
                direction = rt.Point3(0,1,0)
            direction = direction / rt.length(direction)
            target.pos = center
            cam.pos = center - direction * d
        else:
            tm = cam.transform
            direction = -tm.row3
            if float(rt.length(direction)) < 1e-6:
                direction = rt.Point3(0,1,0)
            direction = direction / rt.length(direction)
            cam.transform = rt.Matrix3(
                tm.row1, tm.row2, tm.row3, center - direction * d
            )

        rt.redrawViews()
        return len(nodes)


class Palette(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctrl = Controller()

        self.setWindowTitle("CAMERA VIEW ISOLATE")
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setFixedWidth(300)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10,10,10,10)
        lay.setSpacing(7)

        self.cam_label = QtWidgets.QLabel("Camera: not set")
        self.cam_label.setAlignment(QtCore.Qt.AlignCenter)

        set_cam = QtWidgets.QPushButton("SET THIS CAMERA")
        set_cam.setMinimumHeight(34)

        isolate = QtWidgets.QPushButton("ISOLATE SELECTED IN THIS CAMERA")
        isolate.setMinimumHeight(46)
        isolate.setStyleSheet("QPushButton {font-weight:700; font-size:12px;}")

        restore = QtWidgets.QPushButton("RESTORE CAMERA VIEW")
        restore.setMinimumHeight(34)

        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.HLine)

        title = QtWidgets.QLabel("CAMERA NAVIGATION")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight:700;")

        row = QtWidgets.QHBoxLayout()
        savep = QtWidgets.QPushButton("SAVE P")
        pbtn = QtWidgets.QPushButton("P")
        fit = QtWidgets.QPushButton("FIT SEL")
        row.addWidget(savep)
        row.addWidget(pbtn)
        row.addWidget(fit)

        grid = QtWidgets.QGridLayout()
        defs = [
            ("T", "TOP", 0, 1),
            ("L", "LEFT", 1, 0),
            ("F", "FRONT", 1, 1),
            ("R", "RIGHT", 1, 2),
            ("BK", "BACK", 2, 0),
            ("B", "BOTTOM", 2, 1),
        ]
        for text, view, r, c in defs:
            b = QtWidgets.QPushButton(text)
            b.setMinimumHeight(38)
            b.clicked.connect(lambda checked=False, v=view: self.on_axis(v))
            grid.addWidget(b, r, c)

        self.status = QtWidgets.QLabel(
            "Camera A can be isolated while Camera B remains full."
        )
        self.status.setWordWrap(True)
        self.status.setAlignment(QtCore.Qt.AlignCenter)
        self.status.setMinimumHeight(36)

        self.debug = QtWidgets.QLabel("")
        self.debug.setAlignment(QtCore.Qt.AlignCenter)
        self.debug.setStyleSheet("font-size:9px; color:#999999;")

        safe = QtWidgets.QLabel("VIEWPORT ONLY • RENDERABLE NEVER CHANGED")
        safe.setAlignment(QtCore.Qt.AlignCenter)
        safe.setStyleSheet("font-size:8px; color:#888888;")

        lay.addWidget(self.cam_label)
        lay.addWidget(set_cam)
        lay.addWidget(isolate)
        lay.addWidget(restore)
        lay.addWidget(line)
        lay.addWidget(title)
        lay.addLayout(row)
        lay.addLayout(grid)
        lay.addWidget(self.status)
        lay.addWidget(self.debug)
        lay.addWidget(safe)

        set_cam.clicked.connect(self.on_set_camera)
        isolate.clicked.connect(self.on_isolate)
        restore.clicked.connect(self.on_restore)
        savep.clicked.connect(self.on_save_p)
        pbtn.clicked.connect(self.on_p)
        fit.clicked.connect(self.on_fit)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.update_diag)

    def showEvent(self, e):
        super().showEvent(e)
        QtCore.QTimer.singleShot(0, self.move_east)

    def move_east(self):
        p = self.parentWidget()
        if p is None:
            return
        f = p.frameGeometry()
        self.move(f.x() + f.width() - self.width() - 24, f.y() + 130)

    def fail(self, exc):
        QtWidgets.QMessageBox.warning(self, "CAMERA VIEW ISOLATE", str(exc))

    def on_set_camera(self):
        try:
            c = self.ctrl.set_camera()
            self.cam_label.setText(f"Camera: {c.name}")
            self.status.setText("Camera stored. Now select the objects to keep visible.")
        except Exception as exc:
            self.fail(exc)

    def on_isolate(self):
        try:
            n = self.ctrl.isolate()
            self.status.setText(f"ISOLATED • {n} object(s) visible in this camera only")
            self.timer.start()
            QtCore.QTimer.singleShot(100, self.update_diag)
        except Exception as exc:
            self.fail(exc)

    def on_restore(self):
        try:
            self.ctrl.restore()
            self.timer.stop()
            self.debug.setText("")
            self.status.setText("Camera isolation restored to full scene.")
        except Exception as exc:
            self.fail(exc)

    def on_save_p(self):
        try:
            self.ctrl.save_p()
            self.status.setText("Perspective camera pose saved.")
        except Exception as exc:
            self.fail(exc)

    def on_p(self):
        try:
            self.ctrl.restore_p()
            self.status.setText("Perspective camera pose restored.")
        except Exception as exc:
            self.fail(exc)

    def on_fit(self):
        try:
            n = self.ctrl.fit()
            self.status.setText(f"Camera fitted to {n} selected object(s).")
        except Exception as exc:
            self.fail(exc)

    def on_axis(self, view):
        try:
            n = self.ctrl.axis(view)
            self.status.setText(f"{view.title()} camera direction • framed {n} object(s)")
        except Exception as exc:
            self.fail(exc)

    def update_diag(self):
        try:
            ex, hidden, seen, target = self.ctrl.diagnostics()
            self.debug.setText(
                f"EX {ex} • hidden draws {hidden} • seen camera {seen} / target {target}"
            )
        except Exception:
            pass

    def closeEvent(self, e):
        self.timer.stop()
        try:
            if _DLL is not None and _DLL.CameraVP_IsActive():
                self.ctrl.restore()
        except Exception:
            pass
        super().closeEvent(e)


def show_palette():
    global _WINDOW
    try:
        if _WINDOW is not None:
            _WINDOW.close()
    except Exception:
        pass

    _WINDOW = Palette(qtmax.GetQMaxMainWindow())
    _WINDOW.show()
    _WINDOW.raise_()
    _WINDOW.activateWindow()


show_palette()
