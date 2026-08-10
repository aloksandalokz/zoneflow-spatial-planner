from __future__ import annotations

import ctypes
import math
from pathlib import Path

from pymxs import runtime as rt
from PySide6 import QtCore, QtWidgets
import qtmax

HERE = Path(__file__).resolve().parent
DLL_PATH = HERE / "CameraPerViewportFilter.dll"
_WINDOW = None
_DLL = None


def valid_node(n):
    try:
        return n is not None and bool(rt.isValidNode(n))
    except Exception:
        return False


def is_camera(n):
    if not valid_node(n):
        return False
    try:
        return str(rt.superClassOf(n)).lower() == "camera"
    except Exception:
        return False


def handle(n):
    return int(rt.GetHandleByAnim(n))


def active_camera():
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
        if valid_node(c):
            out.append(c)
            out.extend(descendants(c))
    return out


def expanded_selection():
    seen = set()
    result = []
    for n in list(rt.selection):
        if not valid_node(n) or is_camera(n):
            continue
        for item in [n] + descendants(n):
            try:
                h = handle(item)
            except Exception:
                continue
            if h not in seen:
                seen.add(h)
                result.append(item)
    return result


def bbox(nodes):
    if not nodes:
        raise RuntimeError("Select object(s) first.")
    mn = rt.Point3(1e30, 1e30, 1e30)
    mx = rt.Point3(-1e30, -1e30, -1e30)
    count = 0
    for n in nodes:
        try:
            a, b = n.min, n.max
            mn.x = min(mn.x, a.x); mn.y = min(mn.y, a.y); mn.z = min(mn.z, a.z)
            mx.x = max(mx.x, b.x); mx.y = max(mx.y, b.y); mx.z = max(mx.z, b.z)
            count += 1
        except Exception:
            pass
    if count == 0:
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


def redraw():
    try:
        rt.completeRedraw()
    except Exception:
        rt.redrawViews()


def load_dll():
    global _DLL
    if _DLL is not None:
        return _DLL
    if not DLL_PATH.exists():
        raise RuntimeError("CameraPerViewportFilter.dll is missing beside this Python file.")

    d = ctypes.WinDLL(str(DLL_PATH))
    d.CameraFilter_Isolate.argtypes = [ctypes.c_uint64, ctypes.POINTER(ctypes.c_uint64), ctypes.c_int]
    d.CameraFilter_Isolate.restype = ctypes.c_int
    d.CameraFilter_Restore.argtypes = []
    d.CameraFilter_Restore.restype = ctypes.c_int
    d.CameraFilter_Shutdown.argtypes = []
    d.CameraFilter_Shutdown.restype = ctypes.c_int
    d.CameraFilter_IsActive.argtypes = []
    d.CameraFilter_IsActive.restype = ctypes.c_int
    d.CameraFilter_TargetCamera.argtypes = []
    d.CameraFilter_TargetCamera.restype = ctypes.c_uint64
    d.CameraFilter_LastSeenCamera.argtypes = []
    d.CameraFilter_LastSeenCamera.restype = ctypes.c_uint64
    d.CameraFilter_PreCalls.argtypes = []
    d.CameraFilter_PreCalls.restype = ctypes.c_uint64
    d.CameraFilter_PostCalls.argtypes = []
    d.CameraFilter_PostCalls.restype = ctypes.c_uint64
    d.CameraFilter_FilterCalls.argtypes = []
    d.CameraFilter_FilterCalls.restype = ctypes.c_uint64
    d.CameraFilter_HiddenDecisions.argtypes = []
    d.CameraFilter_HiddenDecisions.restype = ctypes.c_uint64
    d.CameraFilter_SelfTest.argtypes = []
    d.CameraFilter_SelfTest.restype = ctypes.c_int

    if int(d.CameraFilter_SelfTest()) != 1:
        raise RuntimeError("Native camera-filter self-test failed. Do not use this build.")

    _DLL = d
    return d


class Controller:
    def __init__(self):
        self.camera = None
        self.saved_tm = None
        self.saved_target_pos = None
        self.saved_fov = None

    def set_camera(self):
        c = active_camera()
        if c is None:
            raise RuntimeError("Click the camera viewport to isolate, then press SET THIS CAMERA.")
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
        return t if valid_node(t) else None

    def isolate(self):
        cam = self.ensure_camera()
        nodes = expanded_selection()
        if not nodes:
            raise RuntimeError("Select the object(s) you want to KEEP visible in this camera.")
        hs = [handle(n) for n in nodes]
        arr_t = ctypes.c_uint64 * len(hs)
        arr = arr_t(*hs)
        code = int(load_dll().CameraFilter_Isolate(handle(cam), arr, len(hs)))
        if code == -2:
            raise RuntimeError("3ds Max core interface is unavailable.")
        if code != 1:
            raise RuntimeError(f"Camera viewport filter error: {code}")
        redraw()
        return len(nodes)

    def restore(self):
        load_dll().CameraFilter_Restore()
        redraw()

    def diagnostics(self):
        d = load_dll()
        return {
            "pre": int(d.CameraFilter_PreCalls()),
            "post": int(d.CameraFilter_PostCalls()),
            "filter": int(d.CameraFilter_FilterCalls()),
            "hidden": int(d.CameraFilter_HiddenDecisions()),
            "seen": int(d.CameraFilter_LastSeenCamera()),
            "target": int(d.CameraFilter_TargetCamera()),
        }

    def save_p(self):
        cam = self.ensure_camera() if self.camera is None else self.camera
        self.saved_tm = cam.transform
        self.saved_fov = prop_get(cam, "fov", None)
        t = self.target_node(cam)
        self.saved_target_pos = t.pos if t is not None else None

    def restore_p(self):
        cam = self.ensure_camera()
        if self.saved_tm is None:
            raise RuntimeError("No saved perspective camera pose.")
        t = self.target_node(cam)
        if t is not None and self.saved_target_pos is not None:
            t.pos = self.saved_target_pos
        cam.transform = self.saved_tm
        if self.saved_fov is not None:
            prop_set(cam, "fov", self.saved_fov)
        redraw()

    def fit_distance(self, cam, radius):
        try:
            fov = float(prop_get(cam, "fov", 45.0))
        except Exception:
            fov = 45.0
        fov = max(5.0, min(150.0, fov))
        return max(radius / max(math.tan(math.radians(fov * 0.5)), 0.05) * 1.35,
                   radius * 1.8, 10.0)

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
        redraw()
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
            cam.transform = rt.Matrix3(tm.row1, tm.row2, tm.row3, center - direction * d)
        redraw()
        return len(nodes)


class Palette(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctrl = Controller()
        self.setWindowTitle("CAMERA FILTER")
        self.setWindowFlags(QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setFixedWidth(315)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(10,10,10,10)
        lay.setSpacing(7)

        self.cam = QtWidgets.QLabel("Camera: not set")
        self.cam.setAlignment(QtCore.Qt.AlignCenter)
        setcam = QtWidgets.QPushButton("SET THIS CAMERA")
        setcam.setMinimumHeight(34)
        iso = QtWidgets.QPushButton("KEEP ONLY SELECTED IN THIS CAMERA")
        iso.setMinimumHeight(48)
        iso.setStyleSheet("QPushButton {font-weight:700; font-size:12px;}")
        restore = QtWidgets.QPushButton("RESTORE FULL VIEW")
        restore.setMinimumHeight(34)

        title = QtWidgets.QLabel("CAMERA NAVIGATION")
        title.setAlignment(QtCore.Qt.AlignCenter)
        title.setStyleSheet("font-weight:700;")

        prow = QtWidgets.QHBoxLayout()
        savep = QtWidgets.QPushButton("SAVE P")
        pbtn = QtWidgets.QPushButton("P")
        fit = QtWidgets.QPushButton("FIT SEL")
        prow.addWidget(savep); prow.addWidget(pbtn); prow.addWidget(fit)

        grid = QtWidgets.QGridLayout()
        for text, view, r, c in [
            ("T", "TOP", 0, 1),
            ("L", "LEFT", 1, 0),
            ("F", "FRONT", 1, 1),
            ("R", "RIGHT", 1, 2),
            ("BK", "BACK", 2, 0),
            ("B", "BOTTOM", 2, 1),
        ]:
            b = QtWidgets.QPushButton(text)
            b.setMinimumHeight(38)
            b.clicked.connect(lambda checked=False, v=view: self.on_axis(v))
            grid.addWidget(b, r, c)

        self.status = QtWidgets.QLabel("Camera A filtered; other camera viewports remain full.")
        self.status.setWordWrap(True)
        self.status.setAlignment(QtCore.Qt.AlignCenter)
        self.debug = QtWidgets.QLabel("")
        self.debug.setWordWrap(True)
        self.debug.setAlignment(QtCore.Qt.AlignCenter)
        self.debug.setStyleSheet("font-size:9px; color:#999999;")
        safe = QtWidgets.QLabel("VIEWPORT FILTER ONLY • RENDERABLE UNTOUCHED")
        safe.setAlignment(QtCore.Qt.AlignCenter)
        safe.setStyleSheet("font-size:8px; color:#888888;")

        lay.addWidget(self.cam); lay.addWidget(setcam); lay.addWidget(iso); lay.addWidget(restore)
        lay.addWidget(title); lay.addLayout(prow); lay.addLayout(grid)
        lay.addWidget(self.status); lay.addWidget(self.debug); lay.addWidget(safe)

        setcam.clicked.connect(self.on_setcam)
        iso.clicked.connect(self.on_iso)
        restore.clicked.connect(self.on_restore)
        savep.clicked.connect(self.on_savep)
        pbtn.clicked.connect(self.on_p)
        fit.clicked.connect(self.on_fit)

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(400)
        self.timer.timeout.connect(self.update_diag)

        # Load and run native self-test immediately. Fail fast if build is bad.
        load_dll()

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
        QtWidgets.QMessageBox.warning(self, "CAMERA FILTER", str(exc))

    def on_setcam(self):
        try:
            c = self.ctrl.set_camera()
            self.cam.setText(f"Camera: {c.name}")
            self.status.setText("Camera stored. Select what should remain visible.")
        except Exception as e:
            self.fail(e)

    def on_iso(self):
        try:
            n = self.ctrl.isolate()
            self.status.setText(f"ACTIVE • keeping {n} selected object(s) in this camera")
            self.timer.start()
            QtCore.QTimer.singleShot(100, self.update_diag)
        except Exception as e:
            self.fail(e)

    def on_restore(self):
        try:
            self.ctrl.restore()
            self.timer.stop(); self.debug.setText("")
            self.status.setText("Full viewport display restored.")
        except Exception as e:
            self.fail(e)

    def update_diag(self):
        try:
            d = self.ctrl.diagnostics()
            self.debug.setText(
                f"pre {d['pre']} • filter {d['filter']} • hidden {d['hidden']} • "
                f"camera {d['seen']} / target {d['target']}"
            )
        except Exception:
            pass

    def on_savep(self):
        try:
            self.ctrl.save_p(); self.status.setText("Perspective pose saved.")
        except Exception as e:
            self.fail(e)

    def on_p(self):
        try:
            self.ctrl.restore_p(); self.status.setText("Perspective pose restored.")
        except Exception as e:
            self.fail(e)

    def on_axis(self, view):
        try:
            n = self.ctrl.axis(view); self.status.setText(f"{view.title()} camera direction • framed {n} object(s)")
        except Exception as e:
            self.fail(e)

    def on_fit(self):
        try:
            n = self.ctrl.fit(); self.status.setText(f"Camera fitted to {n} object(s).")
        except Exception as e:
            self.fail(e)

    def closeEvent(self, e):
        self.timer.stop()
        try:
            if _DLL is not None:
                _DLL.CameraFilter_Shutdown()
                redraw()
        except Exception:
            pass
        super().closeEvent(e)


def show():
    global _WINDOW
    try:
        if _WINDOW is not None:
            _WINDOW.close()
    except Exception:
        pass
    _WINDOW = Palette(qtmax.GetQMaxMainWindow())
    _WINDOW.show(); _WINDOW.raise_(); _WINDOW.activateWindow()

show()
