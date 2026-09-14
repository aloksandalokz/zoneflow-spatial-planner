from __future__ import annotations

"""3ds Max / PyMXS bridge for Driver Spline Generator.

Usage inside the 3ds Max Python editor:

    import driver_spline_max as dsg
    dsg.start()

Select ONE spline before calling start().
The controller polls the picked driver's knots/handles/transform and rebuilds generated
splines when the driver changes.

Stop:
    dsg.stop()

Manual rebuild:
    dsg.rebuild()

The geometry algorithm lives in driver_spline_core.py and is runnable/testable
outside 3ds Max.
"""

from dataclasses import replace
from typing import Any, List, Optional, Tuple
import builtins

from driver_spline_core import GeneratorSettings, generate_flow_curves

_GLOBAL_KEY = "_DRIVER_SPLINE_GENERATOR_CONTROLLER"


def _load_runtime():
    from pymxs import runtime as rt  # type: ignore
    return rt


def _load_qtimer():
    try:
        from PySide6.QtCore import QTimer  # type: ignore
        return QTimer
    except Exception:
        try:
            from PySide2.QtCore import QTimer  # type: ignore
            return QTimer
        except Exception:
            return None


def _xyz(point: Any) -> Tuple[float, float, float]:
    return (float(point.x), float(point.y), float(point.z))


class DriverSplineGenerator:
    def __init__(
        self,
        driver: Any,
        settings: Optional[GeneratorSettings] = None,
        *,
        runtime: Any = None,
        poll_ms: int = 250,
        auto_watch: bool = True,
    ) -> None:
        self.rt = runtime if runtime is not None else _load_runtime()
        self.driver = driver
        self.settings = settings or GeneratorSettings()
        self.settings.validate()
        self.poll_ms = max(50, int(poll_ms))
        self.outputs: List[Any] = []
        self._timer = None
        self._last_fingerprint = None
        self._rebuilding = False

        self._validate_driver()
        self.rebuild()
        self._last_fingerprint = self.driver_fingerprint()

        if auto_watch:
            self.start_watch()

    def _validate_driver(self) -> None:
        if self.driver is None:
            raise ValueError("No driver spline was supplied.")
        if hasattr(self.rt, "isValidNode") and not self.rt.isValidNode(self.driver):
            raise ValueError("The selected driver is not a valid 3ds Max node.")
        if hasattr(self.rt, "superClassOf"):
            shape_class = getattr(self.rt, "Shape", None)
            if shape_class is not None and self.rt.superClassOf(self.driver) != shape_class:
                raise ValueError("The selected node is not a Shape.")

    def _sample_driver(self, u: float) -> Tuple[float, float, float]:
        point = self.rt.lengthInterp(self.driver, float(u))
        return _xyz(point)

    def _safe_delete(self, node: Any) -> None:
        try:
            if hasattr(self.rt, "isValidNode"):
                if self.rt.isValidNode(node):
                    self.rt.delete(node)
            else:
                self.rt.delete(node)
        except Exception:
            pass

    def clear_outputs(self) -> None:
        for node in list(self.outputs):
            self._safe_delete(node)
        self.outputs = []
        try:
            self.rt.redrawViews()
        except Exception:
            pass

    def _create_shape(self, curve, index: int):
        shape = self.rt.SplineShape()
        try:
            shape.name = "DSG_PY_{:03d}".format(index)
        except Exception:
            pass

        spline_index = self.rt.addNewSpline(shape)
        if spline_index is None:
            spline_index = 1

        knot_type = self.rt.name("smooth")
        segment_type = self.rt.name("curve")

        for x, y, z in curve:
            self.rt.addKnot(
                shape,
                spline_index,
                knot_type,
                segment_type,
                self.rt.point3(float(x), float(y), float(z)),
            )

        self.rt.updateShape(shape)
        return shape

    def rebuild(self) -> List[Any]:
        if self._rebuilding:
            return self.outputs

        self._rebuilding = True
        try:
            self._validate_driver()
            if hasattr(self.rt, "resetLengthInterp"):
                self.rt.resetLengthInterp()

            curves = generate_flow_curves(self._sample_driver, self.settings)

            self.clear_outputs()
            new_outputs = []
            try:
                for i, curve in enumerate(curves, start=1):
                    new_outputs.append(self._create_shape(curve, i))
            except Exception:
                for node in new_outputs:
                    self._safe_delete(node)
                raise

            self.outputs = new_outputs
            try:
                self.rt.redrawViews()
            except Exception:
                pass
            self._last_fingerprint = self.driver_fingerprint()
            return self.outputs
        finally:
            self._rebuilding = False

    def _fingerprint_point(self, p: Any):
        try:
            return (round(float(p.x), 6), round(float(p.y), 6), round(float(p.z), 6))
        except Exception:
            return str(p)

    def driver_fingerprint(self):
        rt = self.rt
        data = []

        try:
            transform = self.driver.transform
            rows = []
            for attr in ("row1", "row2", "row3", "row4"):
                if hasattr(transform, attr):
                    rows.append(self._fingerprint_point(getattr(transform, attr)))
            data.append(tuple(rows) if rows else str(transform))
        except Exception:
            data.append(None)

        try:
            spline_count = int(rt.numSplines(self.driver))
        except Exception:
            spline_count = 1

        data.append(spline_count)

        for spline_index in range(1, spline_count + 1):
            try:
                knot_count = int(rt.numKnots(self.driver, spline_index))
            except Exception:
                knot_count = 0
            data.append(knot_count)

            for knot_index in range(1, knot_count + 1):
                p = rt.getKnotPoint(self.driver, spline_index, knot_index)
                data.append(self._fingerprint_point(p))

                for getter_name in ("getInVec", "getOutVec"):
                    getter = getattr(rt, getter_name, None)
                    if getter is not None:
                        try:
                            data.append(self._fingerprint_point(getter(self.driver, spline_index, knot_index)))
                        except Exception:
                            data.append(None)

        return tuple(data)

    def update_if_changed(self) -> bool:
        if self._rebuilding:
            return False
        current = self.driver_fingerprint()
        if current != self._last_fingerprint:
            self.rebuild()
            return True
        return False

    def start_watch(self) -> bool:
        if self._timer is not None:
            return True
        QTimer = _load_qtimer()
        if QTimer is None:
            return False

        timer = QTimer()
        timer.setInterval(self.poll_ms)
        timer.timeout.connect(self.update_if_changed)
        timer.start()
        self._timer = timer
        return True

    def stop_watch(self) -> None:
        if self._timer is not None:
            try:
                self._timer.stop()
            except Exception:
                pass
            self._timer = None

    def stop(self, *, keep_output: bool = True) -> None:
        self.stop_watch()
        if not keep_output:
            self.clear_outputs()


def _selected_driver(rt):
    selection = list(rt.selection)
    if len(selection) != 1:
        raise RuntimeError("Select exactly ONE spline Shape, then run start().")
    return selection[0]


def start(
    *,
    settings: Optional[GeneratorSettings] = None,
    poll_ms: int = 250,
    auto_watch: bool = True,
) -> DriverSplineGenerator:
    stop(keep_output=True)
    rt = _load_runtime()
    driver = _selected_driver(rt)
    controller = DriverSplineGenerator(driver, settings=settings, runtime=rt, poll_ms=poll_ms, auto_watch=auto_watch)
    setattr(builtins, _GLOBAL_KEY, controller)
    return controller


def controller() -> Optional[DriverSplineGenerator]:
    return getattr(builtins, _GLOBAL_KEY, None)


def rebuild():
    ctl = controller()
    if ctl is None:
        raise RuntimeError("Driver Spline Generator is not running. Call start() first.")
    return ctl.rebuild()


def stop(*, keep_output: bool = True) -> None:
    ctl = controller()
    if ctl is not None:
        ctl.stop(keep_output=keep_output)
        try:
            delattr(builtins, _GLOBAL_KEY)
        except Exception:
            pass


def set_settings(**changes) -> GeneratorSettings:
    ctl = controller()
    if ctl is None:
        raise RuntimeError("Driver Spline Generator is not running. Call start() first.")
    ctl.settings = replace(ctl.settings, **changes)
    ctl.settings.validate()
    ctl.rebuild()
    return ctl.settings
