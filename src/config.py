"""Configuration and India business-hour validation."""

from __future__ import annotations

import os
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

IST = ZoneInfo("Asia/Kolkata")
OFFICE_START = time(9, 0)
OFFICE_END = time(18, 0)


class Settings(BaseModel):
    """Environment-backed settings. Entrypoints call ``load_dotenv`` before construction."""

    livekit_url: str | None = Field(default_factory=lambda: os.getenv("LIVEKIT_URL"))
    livekit_api_key: str | None = Field(default_factory=lambda: os.getenv("LIVEKIT_API_KEY"))
    livekit_api_secret: str | None = Field(default_factory=lambda: os.getenv("LIVEKIT_API_SECRET"))
    livekit_agent_name: str = Field(
        default_factory=lambda: os.getenv("LIVEKIT_AGENT_NAME", "healthcare-outbound-agent")
    )
    stt_model: str = Field(
        default_factory=lambda: os.getenv("STT_MODEL", "deepgram/nova-3-general")
    )
    llm_model: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "openai/gpt-4.1-mini"))
    tts_model: str = Field(default_factory=lambda: os.getenv("TTS_MODEL", "cartesia/sonic-3"))
    tts_voice: str = Field(
        default_factory=lambda: os.getenv(
            "TTS_VOICE", "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"
        )
    )
    opik_api_key: str | None = Field(default_factory=lambda: os.getenv("OPIK_API_KEY"))
    opik_workspace: str | None = Field(default_factory=lambda: os.getenv("OPIK_WORKSPACE"))
    opik_project_name: str = Field(
        default_factory=lambda: os.getenv("OPIK_PROJECT_NAME", "healthcare-voice-agent")
    )
    call_recording_url: str | None = Field(default_factory=lambda: os.getenv("CALL_RECORDING_URL"))
    sip_outbound_trunk_id: str | None = Field(
        default_factory=lambda: os.getenv("SIP_OUTBOUND_TRUNK_ID")
    )
    testing_office_hours_override: bool = Field(
        default_factory=lambda: (
            os.getenv("TESTING_OFFICE_HOURS_OVERRIDE", "false").lower() == "true"
        )
    )


def is_office_hours(now: datetime | None = None) -> bool:
    """Return true only from 09:00 inclusive to 18:00 exclusive, Monday-Friday IST."""
    local = (now or datetime.now(IST)).astimezone(IST)
    return local.weekday() < 5 and OFFICE_START <= local.time() < OFFICE_END


def require_office_hours(settings: Settings, now: datetime | None = None) -> None:
    if not settings.testing_office_hours_override and not is_office_hours(now):
        raise ValueError("Calls are allowed only Monday-Friday, 09:00-18:00 Asia/Kolkata.")
