"""Discrete planning with at most two wedges; no Home Assistant dependencies."""
from itertools import combinations, product
import math

CORNERS = ("front_left", "front_right", "rear_left", "rear_right")


def plan_wedges(longitudinal, transverse, length_m, width_m, stages_cm):
    """Minimize squared residual pitch/roll across zero, one or two wedges.

    The rectangular wheel-support plane is fitted with equal wheel weights:
    pitch changes with mean front minus mean rear lift, roll with mean right
    minus mean left lift. Unequal lifts can twist the suspension; predictions
    are estimates, not a chassis/suspension simulation.
    """
    if not all(math.isfinite(v) for v in (longitudinal, transverse, length_m, width_m)):
        raise ValueError("Angles and dimensions must be finite")
    if length_m <= 0 or width_m <= 0:
        raise ValueError("Dimensions must be positive")
    stages = sorted(set(float(v) for v in stages_cm))
    if not stages or any(not math.isfinite(v) or v <= 0 for v in stages):
        raise ValueError("Wedge stages must be finite positive heights")

    pitch = math.tan(math.radians(longitudinal))
    roll = math.tan(math.radians(transverse))
    length, width = length_m * 100, width_m * 100

    def evaluate(heights):
        fl, fr, rl, rr = heights
        p = math.degrees(math.atan(pitch + (fl + fr - rl - rr) / (2 * length)))
        q = math.degrees(math.atan(roll + (fr + rr - fl - rl) / (2 * width)))
        # Tie breaks: less suspension twist, fewer wedges, less total lift.
        rank = (round(p*p + q*q, 12), abs(fl + rr - fr - rl),
                sum(h > 0 for h in heights), sum(heights))
        return rank, p, q

    best = (0.0, 0.0, 0.0, 0.0)
    rank, p, q = evaluate(best)
    # Avoid introducing a full step for a negligible correction.
    if abs(pitch * length) + abs(roll * width) > 0.5:
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
        "currently_level": abs(pitch * length) + abs(roll * width) <= 0.5,
        "prediction_model": "equal_weight_support_plane",
    }
