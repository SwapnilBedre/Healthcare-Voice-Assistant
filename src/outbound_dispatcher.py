"""Explicit LiveKit SIP dispatcher. Importing/running help never places a call."""

from __future__ import annotations

import argparse
import asyncio
import logging
from uuid import uuid4

from dotenv import load_dotenv

from .config import Settings, require_office_hours

LOGGER = logging.getLogger(__name__)


async def dispatch_outbound_call(phone_number: str, room_name: str | None = None) -> str:
    """Dispatch the agent then create one SIP participant after all safety checks pass."""
    settings = Settings()
    require_office_hours(settings)
    required = {
        "LIVEKIT_URL": settings.livekit_url,
        "LIVEKIT_API_KEY": settings.livekit_api_key,
        "LIVEKIT_API_SECRET": settings.livekit_api_secret,
        "SIP_OUTBOUND_TRUNK_ID": settings.sip_outbound_trunk_id,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(f"Refusing to call: missing {', '.join(missing)}.")
    from livekit import api

    room = room_name or f"healthcare-outbound-{uuid4().hex[:12]}"
    LOGGER.info(
        "preparing outbound dispatch room=%s agent_name=%s", room, settings.livekit_agent_name
    )
    client = api.LiveKitAPI(
        settings.livekit_url, settings.livekit_api_key, settings.livekit_api_secret
    )
    try:
        await client.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=settings.livekit_agent_name, room=room, metadata="demo-outbound-call"
            )
        )
        LOGGER.info("agent dispatch created room=%s", room)
        await client.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                sip_trunk_id=settings.sip_outbound_trunk_id,
                sip_call_to=phone_number,
                room_name=room,
                participant_identity="phone_user",
                participant_name="Demo Outbound Participant",
                wait_until_answered=True,
            )
        )
        LOGGER.info("SIP participant created room=%s", room)
    finally:
        await client.aclose()
        LOGGER.debug("LiveKit API client closed room=%s", room)
    return room


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Explicitly place one LiveKit SIP call.")
    parser.add_argument(
        "--call", action="store_true", help="Required acknowledgement before dialing."
    )
    parser.add_argument("--phone", help="E.164 destination; never log it.")
    parser.add_argument("--room")
    args = parser.parse_args()
    if not args.call or not args.phone:
        parser.error("Refusing to dial. Supply both --call and --phone.")
    room = asyncio.run(dispatch_outbound_call(args.phone, args.room))
    print(f"SIP participant created in room {room}.")


if __name__ == "__main__":
    main()
