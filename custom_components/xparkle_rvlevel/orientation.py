"""Transform upright, inward-facing wall-mounted sensor axes."""
from .const import (
    SENSOR_ORIENTATION_NORMAL, SENSOR_ORIENTATION_ROTATED_180,
    SENSOR_WALL_RIGHT, SENSOR_WALL_LEFT, SENSOR_WALL_FRONT, SENSOR_WALL_REAR,
)


def vehicle_angles(longitudinal: float, transverse: float, orientation: str) -> tuple[float, float]:
    """Return vehicle angles: positive means front high / right side high.

    Right wall is anchored to the observed Berger mounting (legacy 180).
    Front/rear follow rotations around the upright axis, with text upright
    and the sensor face pointing into the vehicle.
    """
    if orientation in (SENSOR_WALL_RIGHT, SENSOR_ORIENTATION_ROTATED_180):
        return -longitudinal, -transverse
    if orientation == SENSOR_WALL_FRONT:
        return -transverse, longitudinal
    if orientation == SENSOR_WALL_REAR:
        return transverse, -longitudinal
    if orientation in (SENSOR_WALL_LEFT, SENSOR_ORIENTATION_NORMAL):
        return longitudinal, transverse
    raise ValueError(f"Unsupported sensor orientation: {orientation}")
