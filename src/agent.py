"""LiveKit voice agent plus a no-credential console flow for safe local testing."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from livekit.agents import RunContext

from .booking_tool import AppointmentBookingService
from .config import IST, Settings
from .models import DemoPatient
from .opik_observability import OpikCallLogger
from .post_call_analysis import analyze_call

LOGGER = logging.getLogger(__name__)


def load_demo_patient() -> DemoPatient:
    records = json.loads((Path(__file__).parent.parent / "data" / "demo_patients.json").read_text())
    return DemoPatient.model_validate(records[0])


def safe_instructions(patient: DemoPatient) -> str:
    supplied = "; ".join(
        f"{item.name.value}: {item.value} {item.unit}" for item in patient.biomarkers
    )
    return f"""You are an English-only healthcare appointment coordinator in India.
Use only these supplied demo biomarker facts: {supplied}.
You may read those values and units exactly. Never diagnose, interpret, compare to ranges,
recommend treatment, claim urgency, or add facts. Say that a clinician can explain the results.
Offer a 30-minute doctor consultation in Asia/Kolkata during weekday business hours (09:00-18:00).
If the person declines or is unavailable, offer rescheduling or a callback. Call book_appointment
only after the person selects a date and time. Do not request or repeat phone numbers."""


def console_flow(action: str, appointment_time: str | None = None) -> dict[str, Any]:
    """Run a deterministic simulated conversation without LiveKit, audio, or credentials."""
    patient = load_demo_patient()
    booking = AppointmentBookingService()
    biomarker_text = ", ".join(f"{b.name.value} {b.value} {b.unit}" for b in patient.biomarkers)
    transcript = (
        f"Agent: Hello {patient.preferred_name}. This is a demo healthcare coordinator. "
        f"The supplied results are {biomarker_text}. A clinician can explain the results. "
        "Would you like a 30-minute doctor consultation?"
    )
    appointment = None
    callback = action == "callback"
    if action == "book":
        if not appointment_time:
            raise ValueError("--appointment-time is required with --action book.")
        selected = datetime.fromisoformat(appointment_time)
        if selected.tzinfo is None:
            raise ValueError("--appointment-time must include a timezone offset, such as +05:30.")
        selected = selected.astimezone(IST)
        appointment = booking.book_appointment(
            patient_id=patient.demo_id,
            patient_name=patient.preferred_name,
            preferred_date=selected.date().isoformat(),
            preferred_time=selected.strftime("%H:%M"),
        )
        transcript += (
            f" Person: Yes. Agent: Your consultation is booked for {appointment.start.isoformat()}."
        )
    elif action == "callback":
        transcript += (
            " Person: I am unavailable; please call back. "
            "Agent: I can arrange a callback or reschedule."
        )
    else:
        transcript += (
            " Person: No thanks. Agent: I can help arrange a callback or reschedule later."
        )
    analysis = analyze_call(transcript, appointment, callback_requested=callback)
    return {
        "transcript": transcript,
        "tool_calls": [x.model_dump() for x in booking.tool_calls],
        "analysis": analysis.model_dump(mode="json"),
    }


def build_livekit_server() -> Any:
    """Construct the actual browser/room agent only when launched in LiveKit worker mode."""
    from livekit.agents import (
        Agent,
        AgentServer,
        AgentSession,
        JobContext,
        function_tool,
        inference,
    )

    settings, patient = Settings(), load_demo_patient()
    LOGGER.info(
        "building LiveKit agent server agent_name=%s stt=%s llm=%s tts=%s",
        settings.livekit_agent_name,
        settings.stt_model,
        settings.llm_model,
        settings.tts_model,
    )
    server = AgentServer()

    class HealthcareAgent(Agent):
        def __init__(self) -> None:
            self.booking = AppointmentBookingService()
            super().__init__(instructions=safe_instructions(patient))

        @function_tool()
        async def book_appointment(
            self,
            context: RunContext,
            preferred_date: str,
            preferred_time: str,
        ) -> dict[str, str | bool]:
            """Book the selected 30-minute doctor consultation in Asia/Kolkata.

            Use YYYY-MM-DD for preferred_date and HH:MM for preferred_time.
            """
            appointment = self.booking.book_appointment(
                patient_id=patient.demo_id,
                patient_name=patient.preferred_name,
                preferred_date=preferred_date,
                preferred_time=preferred_time,
            )
            return self.booking.as_tool_result(appointment)

    @server.rtc_session(agent_name=settings.livekit_agent_name)
    async def entrypoint(ctx: JobContext) -> None:
        # LiveKit Inference keeps model credentials on LiveKit; English is enforced in instructions.
        session = AgentSession(
            stt=inference.STT(model=settings.stt_model, language="en"),
            llm=inference.LLM(model=settings.llm_model, provider="openai"),
            tts=inference.TTS(
                model=settings.tts_model,
                voice=settings.tts_voice,
                language="en",
            ),
        )
        agent = HealthcareAgent()
        logger = OpikCallLogger(settings)
        LOGGER.info(
            "agent job started room=%s agent_name=%s", ctx.room.name, settings.livekit_agent_name
        )

        async def log_at_shutdown(_: str) -> None:
            transcript = json.dumps(session.history.to_dict(), default=str, ensure_ascii=False)
            analysis = analyze_call(transcript, agent.booking.latest_appointment)
            LOGGER.info(
                "agent job shutting down room=%s booked=%s tool_calls=%d",
                ctx.room.name,
                analysis.booked,
                len(agent.booking.tool_calls),
            )
            logger.log_call(
                metadata={
                    "room": ctx.room.name,
                    "timezone": "Asia/Kolkata",
                    "recording_url": settings.call_recording_url,
                },
                patient_variables={
                    "demo_id": patient.demo_id,
                    "biomarkers": [item.model_dump() for item in patient.biomarkers],
                },
                transcript=transcript,
                tool_calls=[record.model_dump() for record in agent.booking.tool_calls],
                analysis=analysis.model_dump(mode="json"),
                recording_url=settings.call_recording_url,
            )

        ctx.add_shutdown_callback(log_at_shutdown)
        await ctx.connect()
        LOGGER.info("agent connected room=%s", ctx.room.name)
        await session.start(agent=agent, room=ctx.room)
        biomarker_summary = ", ".join(
            f"{item.name.value}: {item.value} {item.unit}" for item in patient.biomarkers
        )
        LOGGER.info("agent session started room=%s", ctx.room.name)
        await session.generate_reply(
            instructions=(
                f"Greet {patient.preferred_name} by name and introduce yourself as the healthcare "
                "appointment coordinator. Read every supplied biomarker name, value, and unit "
                f"exactly as provided: {biomarker_summary}. "
                "Do not diagnose, interpret, compare with ranges, recommend treatment, or claim "
                "urgency. Say that a clinician can explain the results, then ask whether the "
                "person would like to schedule a 30-minute consultation."
            )
        )

    return server


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Demo healthcare voice agent")
    parser.add_argument(
        "command", choices=["console", "dev", "start"], help="console requires no credentials"
    )
    parser.add_argument("--action", choices=["book", "decline", "callback"], default="decline")
    parser.add_argument(
        "--appointment-time", help="ISO datetime with offset, e.g. 2026-09-14T10:00:00+05:30"
    )
    args, remaining = parser.parse_known_args()
    if args.command == "console":
        print(
            json.dumps(
                console_flow(args.action, args.appointment_time), indent=2, ensure_ascii=False
            )
        )
        return
    server = build_livekit_server()
    # Forward dev/start and any LiveKit CLI arguments to the current Agents worker CLI.
    import sys

    from livekit.agents import cli

    sys.argv = [sys.argv[0], args.command, *remaining]
    cli.run_app(server)


if __name__ == "__main__":
    main()
