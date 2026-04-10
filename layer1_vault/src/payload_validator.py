from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class TelemetryValidationError(ValueError):
    """Raised when a Layer 0 payload doesn't match the expected contract."""


@dataclass(frozen=True, slots=True)
class TelemetrySummary:
    sequence: int
    timestamp: str
    sensor_id: str
    team: str
    employee_count: int
    avg_focus_score: float
    avg_burnout_risk: float
    avg_activity_load: float
    flags_count: int


def _require_dict(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TelemetryValidationError(f"{field_name} must be an object")
    return value


def _require_list(value: Any, *, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise TelemetryValidationError(f"{field_name} must be a list")
    return value


def _require_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TelemetryValidationError(f"{field_name} must be a non-empty string")
    return value


def _require_int(value: Any, *, field_name: str, minimum: int | None = None) -> int:
    if not isinstance(value, int):
        raise TelemetryValidationError(f"{field_name} must be an integer")
    if minimum is not None and value < minimum:
        raise TelemetryValidationError(f"{field_name} must be >= {minimum}")
    return value


def _require_float(
    value: Any,
    *,
    field_name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if not isinstance(value, (int, float)):
        raise TelemetryValidationError(f"{field_name} must be numeric")
    numeric = float(value)
    if minimum is not None and numeric < minimum:
        raise TelemetryValidationError(f"{field_name} must be >= {minimum}")
    if maximum is not None and numeric > maximum:
        raise TelemetryValidationError(f"{field_name} must be <= {maximum}")
    return numeric


def _validate_employee(employee: Any, *, index: int) -> tuple[float, float, float]:
    record = _require_dict(employee, field_name=f"employees[{index}]")
    _require_str(record.get("user_id"), field_name=f"employees[{index}].user_id")
    _require_str(record.get("display_name"), field_name=f"employees[{index}].display_name")
    focus_score = _require_float(record.get("focus_score"), field_name=f"employees[{index}].focus_score", minimum=0.0, maximum=1.0)
    burnout_risk = _require_float(record.get("burnout_risk"), field_name=f"employees[{index}].burnout_risk", minimum=0.0, maximum=1.0)
    activity_load = _require_float(record.get("activity_load"), field_name=f"employees[{index}].activity_load", minimum=0.0, maximum=1.0)
    _require_int(record.get("context_switches"), field_name=f"employees[{index}].context_switches", minimum=0)
    _require_float(record.get("keystroke_entropy"), field_name=f"employees[{index}].keystroke_entropy", minimum=0.0, maximum=1.0)
    _require_str(record.get("active_window"), field_name=f"employees[{index}].active_window")
    distractions = _require_list(record.get("distractions"), field_name=f"employees[{index}].distractions")
    for distraction_index, distraction in enumerate(distractions):
        _require_str(distraction, field_name=f"employees[{index}].distractions[{distraction_index}]")
    flow_minutes = record.get("flow_minutes")
    if flow_minutes is not None:
        _require_int(flow_minutes, field_name=f"employees[{index}].flow_minutes", minimum=0)
    return (focus_score, burnout_risk, activity_load)


def validate_telemetry_payload(payload: Any) -> TelemetrySummary:
    root = _require_dict(payload, field_name="payload")
    timestamp = _require_str(root.get("timestamp"), field_name="timestamp")
    sequence = _require_int(root.get("sequence"), field_name="sequence", minimum=0)
    sensor_id = _require_str(root.get("sensor_id"), field_name="sensor_id")
    team = _require_str(root.get("team"), field_name="team")
    employees = _require_list(root.get("employees"), field_name="employees")
    if not employees:
        raise TelemetryValidationError("employees must contain at least one record")

    system_load = _require_dict(root.get("system_load"), field_name="system_load")
    _require_float(system_load.get("cpu"), field_name="system_load.cpu")
    _require_float(system_load.get("memory"), field_name="system_load.memory")
    _require_float(system_load.get("network_mbps"), field_name="system_load.network_mbps")

    flags = _require_list(root.get("flags"), field_name="flags")
    for flag_index, flag in enumerate(flags):
        _require_str(flag, field_name=f"flags[{flag_index}]")

    focus_total = 0.0
    burnout_total = 0.0
    activity_total = 0.0
    for employee_index, employee in enumerate(employees):
        focus_score, burnout_risk, activity_load = _validate_employee(employee, index=employee_index)
        focus_total += focus_score
        burnout_total += burnout_risk
        activity_total += activity_load

    employee_count = len(employees)
    return TelemetrySummary(
        sequence=sequence,
        timestamp=timestamp,
        sensor_id=sensor_id,
        team=team,
        employee_count=employee_count,
        avg_focus_score=round(focus_total / employee_count, 6),
        avg_burnout_risk=round(burnout_total / employee_count, 6),
        avg_activity_load=round(activity_total / employee_count, 6),
        flags_count=len(flags),
    )
