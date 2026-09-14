from __future__ import annotations
from dataclasses import dataclass
import math
import random
from typing import Callable, Sequence, Tuple, List

Vec3 = Tuple[float, float, float]

def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])

def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])

def _mul(v: Vec3, s: float) -> Vec3:
    return (v[0]*s, v[1]*s, v[2]*s)

def _length(v: Vec3) -> float:
    return math.sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2])

def _normalize(v: Vec3) -> Vec3:
    n = _length(v)
    if n <= 1e-12:
        return (0.0, 0.0, 0.0)
    return (v[0]/n, v[1]/n, v[2]/n)

@dataclass(frozen=True)
class GeneratorSettings:
    sample_spacing: float = 0.1
    seed: int = 12345
    random_min: Vec3 = (-100.0, -100.0, -100.0)
    random_max: Vec3 = (100.0, 100.0, 100.0)
    iterations: int = 200
    step: float = 1.0
    threshold: int = 0
    knot_every: int = 1
    drop_last_curve: bool = True

    def validate(self) -> None:
        if not (0.001 <= self.sample_spacing <= 1.0):
            raise ValueError("sample_spacing must be in [0.001, 1.0]")
        if self.iterations < 1:
            raise ValueError("iterations must be >= 1")
        if self.step <= 0:
            raise ValueError("step must be > 0")
        if self.threshold < 0:
            raise ValueError("threshold must be >= 0")
        if self.knot_every < 1:
            raise ValueError("knot_every must be >= 1")
        for lo, hi, axis in zip(self.random_min, self.random_max, "XYZ"):
            if lo > hi:
                raise ValueError(f"random_min.{axis} must be <= random_max.{axis}")

def sample_parameters(spacing: float) -> List[float]:
    if spacing <= 0 or spacing > 1:
        raise ValueError("spacing must be in (0, 1]")
    values: List[float] = []
    u = 0.0
    while u <= 1.0 + 1e-9:
        values.append(min(u, 1.0))
        u += spacing
    if values[-1] < 1.0 - 1e-9:
        values.append(1.0)
    deduped: List[float] = []
    for v in values:
        if not deduped or abs(v - deduped[-1]) > 1e-9:
            deduped.append(v)
    return deduped

def generate_flow_curves(
    driver_sampler: Callable[[float], Vec3],
    settings: GeneratorSettings,
) -> List[List[Vec3]]:
    settings.validate()
    rng = random.Random(settings.seed)

    starts: List[Vec3] = []
    for u in sample_parameters(settings.sample_spacing):
        base = driver_sampler(u)
        offset = (
            rng.uniform(settings.random_min[0], settings.random_max[0]),
            rng.uniform(settings.random_min[1], settings.random_max[1]),
            rng.uniform(settings.random_min[2], settings.random_max[2]),
        )
        starts.append(_add(base, offset))

    if len(starts) < 2:
        return []

    current = list(starts)
    curves: List[List[Vec3]] = [[] for _ in current]

    for iteration in range(1, settings.iterations + 1):
        for p in range(len(current)):
            target_index = p + 1 if p < len(current) - 1 else 0
            delta = _sub(current[target_index], current[p])
            if _length(delta) > 1e-12:
                current[p] = _add(current[p], _mul(_normalize(delta), settings.step))

            if iteration >= settings.threshold:
                if ((iteration - settings.threshold) % settings.knot_every) == 0:
                    curves[p].append(current[p])

    repaired: List[List[Vec3]] = []
    for curve in curves:
        if not curve:
            continue
        if len(curve) == 1:
            p = curve[0]
            curve = [p, (p[0] + 1e-4, p[1], p[2])]
        repaired.append(curve)

    if settings.drop_last_curve and len(repaired) > 1:
        repaired = repaired[:-1]

    return repaired

def polyline_sampler(points: Sequence[Vec3]) -> Callable[[float], Vec3]:
    if len(points) < 2:
        raise ValueError("At least two points are required")
    seg_lengths = []
    cumulative = [0.0]
    total = 0.0
    for a, b in zip(points, points[1:]):
        d = _length(_sub(b, a))
        seg_lengths.append(d)
        total += d
        cumulative.append(total)
    if total <= 1e-12:
        raise ValueError("Polyline length must be > 0")

    def sample(u: float) -> Vec3:
        u = max(0.0, min(1.0, float(u)))
        target = u * total
        if target >= total:
            return tuple(map(float, points[-1]))
        for i, seg_len in enumerate(seg_lengths):
            if cumulative[i+1] >= target:
                if seg_len <= 1e-12:
                    return tuple(map(float, points[i]))
                t = (target - cumulative[i]) / seg_len
                a, b = points[i], points[i+1]
                return (
                    a[0] + (b[0]-a[0])*t,
                    a[1] + (b[1]-a[1])*t,
                    a[2] + (b[2]-a[2])*t,
                )
        return tuple(map(float, points[-1]))

    return sample
