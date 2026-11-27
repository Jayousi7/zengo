"""Flight paths: smooth curves through waypoints, walked at an even speed.

A path is built once when Zengo takes off. Waypoints are joined with a
centripetal Catmull-Rom spline, which passes through every waypoint without the
loops and overshoots a plain spline makes when points are unevenly spaced. The
curve is then sampled densely and measured, so the flight can be driven by
distance flown rather than by spline parameter, which would speed up and slow
down from one segment to the next.
"""

from __future__ import annotations

import bisect
import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass

Point = tuple[float, float]


def ease(p: float) -> float:
    """Share of the path flown at time fraction ``p``: a mild ease in and out, so
    takeoff and landing are a little slower without ever coming to a hover."""
    return 0.6 * p + 0.4 * p * p * (3 - 2 * p)


@dataclass(frozen=True)
class FlightPath:
    points: tuple[Point, ...]
    distances: tuple[float, ...]
    """Distance along the path at each of ``points``; starts at 0."""

    @classmethod
    def through(
        cls, waypoints: Sequence[Point], *, top: float, bottom: float, samples: int = 16
    ) -> FlightPath:
        """Curve through ``waypoints``, kept between ``top`` and ``bottom`` (screen y).

        The clamp stops a curve from dipping below the ground between waypoints
        or rising off the top of the screen.
        """
        if len(waypoints) < 2:
            raise ValueError("a flight needs at least a start and an end")
        pts = list(waypoints)
        padded = [_mirror(pts[1], pts[0]), *pts, _mirror(pts[-2], pts[-1])]
        curve: list[Point] = []
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = padded[i : i + 4]
            curve.extend(_segment(p0, p1, p2, p3, samples))
        curve.append(pts[-1])
        curve = [(x, min(max(y, top), bottom)) for x, y in curve]

        distances = [0.0]
        for a, b in itertools.pairwise(curve):
            distances.append(distances[-1] + math.dist(a, b))
        return cls(tuple(curve), tuple(distances))

    @property
    def length(self) -> float:
        return self.distances[-1]

    def at(self, s: float) -> Point:
        """Position after flying distance ``s`` along the path."""
        s = min(max(s, 0.0), self.length)
        i = max(bisect.bisect_right(self.distances, s) - 1, 0)
        if i >= len(self.points) - 1:
            return self.points[-1]
        span = self.distances[i + 1] - self.distances[i]
        t = (s - self.distances[i]) / span if span else 0.0
        (x0, y0), (x1, y1) = self.points[i], self.points[i + 1]
        return x0 + (x1 - x0) * t, y0 + (y1 - y0) * t

    def heading(self, s: float, ahead: float) -> Point:
        """Direction of travel at ``s``, as the offset to the point ``ahead`` further on."""
        x0, y0 = self.at(s)
        x1, y1 = self.at(s + ahead)
        if (x1, y1) == (x0, y0):  # at the very end: look back instead
            xb, yb = self.at(s - ahead)
            return x0 - xb, y0 - yb
        return x1 - x0, y1 - y0


def _mirror(p: Point, about: Point) -> Point:
    """Phantom point beyond an end of the path, so the curve leaves it straight."""
    return 2 * about[0] - p[0], 2 * about[1] - p[1]


def _segment(p0: Point, p1: Point, p2: Point, p3: Point, samples: int) -> list[Point]:
    """Points from ``p1`` up to (not including) ``p2`` on a centripetal Catmull-Rom curve."""

    def knot(t: float, a: Point, b: Point) -> float:
        return t + max(math.dist(a, b), 1e-6) ** 0.5

    t0 = 0.0
    t1 = knot(t0, p0, p1)
    t2 = knot(t1, p1, p2)
    t3 = knot(t2, p2, p3)

    def lerp(a: Point, b: Point, ta: float, tb: float, t: float) -> Point:
        u = (t - ta) / (tb - ta)
        return a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u

    out = []
    for k in range(samples):
        t = t1 + (t2 - t1) * k / samples
        a1 = lerp(p0, p1, t0, t1, t)
        a2 = lerp(p1, p2, t1, t2, t)
        a3 = lerp(p2, p3, t2, t3, t)
        b1 = lerp(a1, a2, t0, t2, t)
        b2 = lerp(a2, a3, t1, t3, t)
        out.append(lerp(b1, b2, t1, t2, t))
    return out
