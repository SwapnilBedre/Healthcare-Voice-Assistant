"""Local simulated appointment-booking tool.

This module keeps the booking flow fully local and writes successful demo
appointments to a JSON file so the appointment record persists in the project.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, time, timedelta
from pathlib import Path
from uuid import uuid4

from .config import IST, is_office_hours
from .models import Appointment, AppointmentRequest, ToolCallRecord

DEFAULT_APPOINTMENTS_FILE = Path(__file__).parent.parent / "data" / "appointments.json"
APPOINTMENT_DURATION = timedelta(minutes=30)
LOGGER = logging.getLogger(__name__)


class AppointmentConflictError(ValueError):
    """Raised when the requested 30-minute slot is already booked."""


def book_appointment(
    patient_id: str,
    patient_name: str,
    preferred_date: str,
    preferred_time: str,
    storage_path: str | Path | None = None,
) -> dict[str, str | bool]:
    """Book a local appointment and persist it to the project JSON store."""
    service = AppointmentBookingService(storage_path=Path(storage_path) if storage_path else None)
    appointment = service.book_appointment(
        patient_id=patient_id,
        patient_name=patient_name,
        preferred_date=preferred_date,
        preferred_time=preferred_time,
    )
    return service.as_tool_result(appointment)


class AppointmentBookingService:
    """Books simulated appointments and keeps a small local JSON history."""

    def __init__(self, storage_path: Path | None = None) -> None:
        # Resolve the default here so callers can provide a separate storage path.
        self.storage_path = storage_path or DEFAULT_APPOINTMENTS_FILE
        self.tool_calls: list[ToolCallRecord] = []
        self.latest_appointment: Appointment | None = None

    def book_appointment(
        self,
        patient_id: str,
        patient_name: str,
        preferred_date: str,
        preferred_time: str,
    ) -> Appointment:
        """Simulate booking a 30-minute appointment and save it to appointments.json.

        ``preferred_date`` must look like ``2026-09-14`` and ``preferred_time``
        must look like ``10:00``. The chosen time is treated as Asia/Kolkata time.
        """
        request = AppointmentRequest(
            patient_id=patient_id,
            patient_name=patient_name,
            preferred_date=preferred_date,
            preferred_time=preferred_time,
        )
        start = datetime.combine(request.preferred_date, request.preferred_time, IST)
        office_end = datetime.combine(request.preferred_date, time(18, 0), IST)
        if not is_office_hours(start) or start + APPOINTMENT_DURATION > office_end:
            raise ValueError(
                f"The requested slot {request.preferred_date.isoformat()} "
                f"{request.preferred_time.strftime('%H:%M')} is outside weekday "
                "09:00-17:30 appointment hours in Asia/Kolkata."
            )

        appointment = Appointment(
            appointment_id=f"APT-{uuid4().hex[:8]}",
            patient_id=request.patient_id,
            patient_name=request.patient_name,
            date=request.preferred_date,
            time=request.preferred_time,
        )
        if self._slot_is_booked(appointment):
            raise AppointmentConflictError(
                f"The slot {request.preferred_date.isoformat()} "
                f"{request.preferred_time.strftime('%H:%M')} Asia/Kolkata is already booked."
            )
        self._append_to_file(appointment)
        self.latest_appointment = appointment
        LOGGER.info(
            "appointment booked appointment_id=%s date=%s time=%s",
            appointment.appointment_id,
            appointment.date.isoformat(),
            appointment.time.strftime("%H:%M"),
        )
        self.tool_calls.append(
            ToolCallRecord(
                name="book_appointment",
                arguments={
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "preferred_date": preferred_date,
                    "preferred_time": preferred_time,
                },
                result=self.as_tool_result(appointment),
            )
        )
        return appointment

    def _slot_is_booked(self, appointment: Appointment) -> bool:
        """Return whether the requested 30-minute interval overlaps a booking."""
        if not self.storage_path.exists():
            return False
        try:
            records = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("appointments.json is not valid JSON; fix it before booking.") from exc
        if not isinstance(records, list):
            raise ValueError("appointments.json must contain a JSON list.")
        requested_start = datetime.combine(appointment.date, appointment.time, IST)
        requested_end = requested_start + APPOINTMENT_DURATION
        for record in records:
            if not isinstance(record, dict) or record.get("status") != "BOOKED":
                continue
            if record.get("date") != appointment.date.isoformat():
                continue
            try:
                existing_time = datetime.strptime(record["time"], "%H:%M").time()
            except (KeyError, TypeError, ValueError):
                continue
            existing_start = datetime.combine(appointment.date, existing_time, IST)
            existing_end = existing_start + APPOINTMENT_DURATION
            if existing_start < requested_end and requested_start < existing_end:
                return True
        return False

    def _append_to_file(self, appointment: Appointment) -> None:
        """Create the data folder/file when needed, then append one appointment."""
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self.storage_path.write_text("[]\n", encoding="utf-8")
        try:
            records = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("appointments.json is not valid JSON; fix it before booking.") from exc
        if not isinstance(records, list):
            raise ValueError("appointments.json must contain a JSON list.")
        records.append(self.as_tool_result(appointment))
        self.storage_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")

    @staticmethod
    def as_tool_result(appointment: Appointment) -> dict[str, str | bool]:
        """Return the simple structured response used by the agent function tool."""
        return {
            "success": True,
            "appointment_id": appointment.appointment_id,
            "patient_id": appointment.patient_id,
            "patient_name": appointment.patient_name,
            "date": appointment.date.isoformat(),
            "time": appointment.time.strftime("%H:%M"),
            "status": appointment.status.value,
        }
