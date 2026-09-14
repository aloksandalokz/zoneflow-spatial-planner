import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from driver_spline_core import GeneratorSettings, generate_flow_curves, polyline_sampler, sample_parameters
from driver_spline_max import DriverSplineGenerator


def test_sample_parameters_includes_end():
    assert sample_parameters(0.25) == [0.0, 0.25, 0.5, 0.75, 1.0]
    vals = sample_parameters(0.3)
    assert vals[0] == 0.0
    assert vals[-1] == 1.0


def test_core_is_deterministic_for_same_seed():
    sampler = polyline_sampler([(0, 0, 0), (100, 0, 0), (200, 50, 0)])
    settings = GeneratorSettings(sample_spacing=0.25, seed=77, random_min=(-10, -10, 0), random_max=(10, 10, 0), iterations=20, step=1.0, threshold=0, knot_every=2)
    a = generate_flow_curves(sampler, settings)
    b = generate_flow_curves(sampler, settings)
    assert a == b
    assert len(a) == 4
    assert all(len(curve) >= 2 for curve in a)


def test_driver_shape_change_changes_result_but_seed_stays_stable():
    settings = GeneratorSettings(sample_spacing=0.5, seed=5, random_min=(-2, -2, 0), random_max=(2, 2, 0), iterations=5, step=0.5, drop_last_curve=False)
    straight = generate_flow_curves(polyline_sampler([(0, 0, 0), (100, 0, 0)]), settings)
    bent = generate_flow_curves(polyline_sampler([(0, 0, 0), (50, 50, 0), (100, 0, 0)]), settings)
    assert straight != bent
    assert len(straight) == len(bent)


class P3:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Matrix:
    def __init__(self):
        self.row1 = P3(1, 0, 0)
        self.row2 = P3(0, 1, 0)
        self.row3 = P3(0, 0, 1)
        self.row4 = P3(0, 0, 0)


class Driver:
    def __init__(self, points):
        self.points = [P3(*p) for p in points]
        self.in_vecs = [P3(*p) for p in points]
        self.out_vecs = [P3(*p) for p in points]
        self.transform = Matrix()
        self.valid = True


class Shape:
    def __init__(self):
        self.name = ""
        self.splines = []
        self.valid = True


class FakeRuntime:
    Shape = "Shape"

    def __init__(self, driver):
        self.driver = driver
        self.selection = [driver]
        self.created = []
        self.deleted = []
        self.reset_calls = 0
        self.redraw_calls = 0

    def isValidNode(self, node):
        return getattr(node, "valid", False)

    def superClassOf(self, node):
        return self.Shape if isinstance(node, Driver) else "Other"

    def resetLengthInterp(self):
        self.reset_calls += 1

    def numSplines(self, node):
        return 1

    def numKnots(self, node, spline_index):
        return len(node.points)

    def getKnotPoint(self, node, spline_index, knot_index):
        return node.points[knot_index - 1]

    def getInVec(self, node, spline_index, knot_index):
        return node.in_vecs[knot_index - 1]

    def getOutVec(self, node, spline_index, knot_index):
        return node.out_vecs[knot_index - 1]

    def _polyline_sample(self, u):
        pts = [(p.x, p.y, p.z) for p in self.driver.points]
        lens = []
        total = 0.0
        for a, b in zip(pts, pts[1:]):
            d = math.dist(a, b)
            lens.append(d)
            total += d
        target = max(0.0, min(1.0, float(u))) * total
        acc = 0.0
        for i, d in enumerate(lens):
            if acc + d >= target or i == len(lens) - 1:
                t = 0.0 if d == 0 else (target - acc) / d
                a, b = pts[i], pts[i + 1]
                return P3(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)
            acc += d
        return P3(*pts[-1])

    def lengthInterp(self, node, u):
        assert node is self.driver
        return self._polyline_sample(u)

    def SplineShape(self):
        s = Shape()
        self.created.append(s)
        return s

    def addNewSpline(self, shape):
        shape.splines.append([])
        return len(shape.splines)

    def name(self, value):
        return value

    def point3(self, x, y, z):
        return P3(x, y, z)

    def addKnot(self, shape, spline_index, knot_type, segment_type, point):
        assert knot_type == "smooth"
        assert segment_type == "curve"
        shape.splines[spline_index - 1].append(point)

    def updateShape(self, shape):
        assert shape.splines and len(shape.splines[0]) >= 2

    def delete(self, node):
        node.valid = False
        self.deleted.append(node)

    def redrawViews(self):
        self.redraw_calls += 1


def test_max_bridge_builds_valid_splines_with_mocked_pymxs_contract():
    driver = Driver([(0, 0, 0), (100, 0, 0), (200, 50, 0)])
    rt = FakeRuntime(driver)
    settings = GeneratorSettings(sample_spacing=0.25, seed=11, random_min=(0, 0, 0), random_max=(0, 0, 0), iterations=10, step=1.0, knot_every=1)
    ctl = DriverSplineGenerator(driver, settings, runtime=rt, auto_watch=False)
    assert rt.reset_calls == 1
    assert len(ctl.outputs) == 4
    assert all(len(s.splines) == 1 for s in ctl.outputs)
    assert all(len(s.splines[0]) >= 2 for s in ctl.outputs)


def test_max_bridge_rebuilds_when_driver_knot_moves():
    driver = Driver([(0, 0, 0), (100, 0, 0), (200, 0, 0)])
    rt = FakeRuntime(driver)
    settings = GeneratorSettings(sample_spacing=0.5, seed=22, random_min=(0, 0, 0), random_max=(0, 0, 0), iterations=8, step=1.0)
    ctl = DriverSplineGenerator(driver, settings, runtime=rt, auto_watch=False)
    before = [[(p.x, p.y, p.z) for p in s.splines[0]] for s in ctl.outputs]
    reset_before = rt.reset_calls
    driver.points[1].y = 80.0
    assert ctl.update_if_changed() is True
    after = [[(p.x, p.y, p.z) for p in s.splines[0]] for s in ctl.outputs]
    assert rt.reset_calls == reset_before + 1
    assert before != after


def test_max_bridge_detects_bezier_handle_only_edit():
    driver = Driver([(0, 0, 0), (100, 0, 0), (200, 0, 0)])
    rt = FakeRuntime(driver)
    ctl = DriverSplineGenerator(driver, GeneratorSettings(sample_spacing=0.5, random_min=(0, 0, 0), random_max=(0, 0, 0), iterations=3), runtime=rt, auto_watch=False)
    fp_before = ctl.driver_fingerprint()
    driver.out_vecs[1].y = 25.0
    fp_after = ctl.driver_fingerprint()
    assert fp_before != fp_after


def test_bridge_module_compiles_without_pymxs_installed():
    source = (ROOT / "driver_spline_max.py").read_text(encoding="utf-8")
    compile(source, "driver_spline_max.py", "exec")
