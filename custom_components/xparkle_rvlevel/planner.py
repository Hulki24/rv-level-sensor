"""Discrete planning with at most two wedges; no Home Assistant dependencies."""
from itertools import combinations, product
import math

CORNERS = ("front_left", "front_right", "rear_left", "rear_right")


def corner_heights(longitudinal, transverse, length_m, front_width_m, rear_width_m):
    """Physical heights relative to the axle-centre midpoint, in centimetres."""
    p = math.tan(math.radians(longitudinal)) * length_m * 50
    q = math.tan(math.radians(transverse))
    front = q * front_width_m * 50
    rear = q * rear_width_m * 50
    return dict(zip(CORNERS, (p-front, p+front, -p-rear, -p+rear)))


def plan_wedges(longitudinal, transverse, length_m, width_m, stages_cm, rear_width_m=None):
    """Minimize squared residual pitch/roll across zero, one or two wedges.

    The trapezoidal wheel-support plane is fitted with equal wheel weights:
    pitch changes with mean front minus mean rear lift. Roll is the fitted
    lateral slope at the actual front and rear wheel positions. Unequal lifts can twist the suspension; predictions
    are estimates, not a chassis/suspension simulation.
    """
    rear_width_m = width_m if rear_width_m is None else rear_width_m
    if not all(math.isfinite(v) for v in (longitudinal, transverse, length_m, width_m, rear_width_m)):
        raise ValueError("Angles and dimensions must be finite")
    if length_m <= 0 or width_m <= 0 or rear_width_m <= 0:
        raise ValueError("Dimensions must be positive")
    stages = sorted(set(float(v) for v in stages_cm))
    if not stages or any(not math.isfinite(v) or v <= 0 for v in stages):
        raise ValueError("Wedge stages must be finite positive heights")

    pitch = math.tan(math.radians(longitudinal))
    roll = math.tan(math.radians(transverse))
    length, width, rear_width = length_m * 100, width_m * 100, rear_width_m * 100
    physical = corner_heights(longitudinal, transverse, length_m, width_m, rear_width_m)
    currently_level = max(physical.values()) - min(physical.values()) <= 0.5

    def evaluate(heights):
        fl, fr, rl, rr = heights
        p = math.degrees(math.atan(pitch + (fl + fr - rl - rr) / (2 * length)))
        q = math.degrees(math.atan(roll + (width * (fr - fl) + rear_width * (rr - rl)) / (width**2 + rear_width**2)))
        # Tie breaks: less suspension twist, fewer wedges, less total lift.
        rank = (round(p*p + q*q, 12), abs(rear_width * (fr - fl) - width * (rr - rl)),
                sum(h > 0 for h in heights), sum(heights))
        return rank, p, q

    best = (0.0, 0.0, 0.0, 0.0)
    rank, p, q = evaluate(best)
    # Avoid introducing a full step for a negligible correction.
    if not currently_level:
        for count in (1, 2):
            for wheels in combinations(range(4), count):
                for heights in product(stages, repeat=count):
                    candidate = [0.0] * 4
                    for wheel, height in zip(wheels, heights):
                        candidate[wheel] = height
                    candidate_rank, cp, cq = evaluate(candidate)
                    if candidate_rank < rank:
                        best, rank, p, q = candidate, candidate_rank, cp, cq
    return {
        "heights_cm": dict(zip(CORNERS, best)),
        "stages": {key: stages.index(h) + 1 if h else 0
                   for key, h in zip(CORNERS, best)},
        "residual_longitudinal_angle": round(p, 3),
        "residual_transverse_angle": round(q, 3),
        "residual_total_angle": round(math.degrees(math.atan(math.hypot(
            math.tan(math.radians(p)), math.tan(math.radians(q))))), 3),
        "wedge_limit": 2,
        "currently_level": currently_level,
        "front_track_width_m": width_m,
        "rear_track_width_m": rear_width_m,
        "prediction_model": "equal_weight_support_plane",
    }
