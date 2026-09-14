"""Pydantic models shared by the demo agent. No real patient data belongs here."""

from __future__ import annotations

from datetime import date, time
from enum import StrEnum

from pydantic import BaseModel, Field


class BiomarkerName(StrEnum):
    HBA1C = "HbA1c"
    FASTING_INSULIN = "fasting insulin"
    APOB = "ApoB"
    EGFR = "eGFR"
    ALT = "ALT"
    FASTING_GLUCOSE = "fasting glucose"


class BiomarkerValue(BaseModel):
    name: BiomarkerName
    value: str = Field(description="Supplied display value; never calculate or alter it.")
    unit: str = Field(min_length=1, description="Supplied display unit; state it verbatim.")


class DemoPatient(BaseModel):
    """Synthetic, non-identifying test record."""

    demo_id: str
    preferred_name: str
    biomarkers: list[BiomarkerValue]


class AppointmentStatus(StrEnum):
    BOOKED = "BOOKED"
    NOT_BOOKED = "NOT_BOOKED"


class AppointmentRequest(BaseModel):
    """The information collected before using the simulated booking tool."""

    patient_id: str
    patient_name: str
    preferred_date: date
    preferred_time: time


class Appointment(BaseModel):
    """The local appointment record that is stored in ``data/appointments.json``."""

    appointment_id: str
    patient_id: str
    patient_name: str
    date: date
    time: time
    status: AppointmentStatus = AppointmentStatus.BOOKED


class ToolCallRecord(BaseModel):
    name: str
    arguments: dict[str, str] = Field(default_factory=dict)
    result: dict[str, str | bool] = Field(default_factory=dict)


class PostCallAnalysis(BaseModel):
    booked: bool
    selected_appointment_time: str | None = None
    reason_not_booked: str | None = None
    reschedule_or_callback_requested: bool = False
    concise_summary: str
