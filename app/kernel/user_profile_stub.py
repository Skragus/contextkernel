"""Stub backup config for user / goals tuning.

This is *not* wired into the kernel yet. It mirrors what you might
eventually drive from environment variables or an external profile
service.

For now it serves as:
- Documentation for which knobs exist.
- A convenient place to experiment in notebooks/tests.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UserProfile:
    age: int | None = None
    height_cm: float | None = None
    sex: str | None = None  # "male" | "female" | other
    activity_level: str | None = None  # "sedentary" | "light" | "moderate" | "active" | "very_active"

    # Optional notes that an agent can interpret (not parsed by kernel).
    injury_notes: str | None = None
    medical_conditions: list[str] | None = None

    # Goal-related overrides (all optional)
    tdee_override: float | None = None
    step_target_override: float | None = None
    calorie_deficit_override: float | None = None
    steps_floor_override: float | None = None
    ramp_rate_fast: float | None = None
    ramp_rate_slow: float | None = None


# Example stub instance (not imported anywhere by default)
EXAMPLE_USER_PROFILE = UserProfile(
    age=None,
    height_cm=None,
    sex=None,
    activity_level=None,
    injury_notes=None,
    medical_conditions=None,
)

