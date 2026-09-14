"""
Run ``python main.py`` after installing the project. This menu only exercises the
safe local appointment-booking flow. It cannot make a phone call.
"""

from __future__ import annotations

import json

from src.agent import console_flow


def main() -> None:
    """Ask for a demo outcome and show the resulting transcript and analysis."""
    print("Healthcare Voice Agent - Safe Demo Mode")
    print("1. Book a consultation")
    print("2. Decline consultation")
    print("3. Request callback")
    choice = input("Choose 1, 2, or 3: ").strip()

    if choice == "1":
        appointment_time = input(
            "Enter an IST time, for example 2026-09-14T10:00:00+05:30: "
        ).strip()
        result = console_flow("book", appointment_time)
    elif choice == "2":
        result = console_flow("decline")
    elif choice == "3":
        result = console_flow("callback")
    else:
        print("Please run the program again and choose 1, 2, or 3.")
        return

    print("\nDemo result:")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
