def clamp_volume(value: float) -> float:
    return max(0.0, min(1.0, value))
