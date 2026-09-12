"""Deterministic post-call outcome extraction. It avoids sending transcripts to another model."""

from __future__ import annotations

from .models import Appointment, PostCallAnalysis


def analyze_call(
    transcript: str, appointment: Appointment | None, *, callback_requested: bool = False
) -> PostCallAnalysis:
    """Produce auditable post-call fields from the actual booking result and transcript."""
    compact = " ".join(transcript.split())
    if appointment:
        return PostCallAnalysis(
            booked=True,
            selected_appointment_time=(
                f"{appointment.date.isoformat()} {appointment.time.strftime('%H:%M')} Asia/Kolkata"
            ),
            reschedule_or_callback_requested=False,
            concise_summary="Consultation booked for the selected time.",
        )
    lower = compact.lower()
    unavailable = any(word in lower for word in ("unavailable", "busy", "call back", "callback"))
    declined = any(word in lower for word in ("decline", "not interested", "no thanks"))
    reason = (
        "person unavailable"
        if unavailable
        else "consultation declined"
        if declined
        else "no appointment selected"
    )
    return PostCallAnalysis(
        booked=False,
        reason_not_booked=reason,
        reschedule_or_callback_requested=callback_requested or unavailable or "reschedule" in lower,
        concise_summary=f"No consultation booked: {reason}.",
    )
