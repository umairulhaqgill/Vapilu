"""
Creates example flows so the shape of a real flow is concrete.

Run after seed_tenants.py:
    python seed_flows.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ.get("TENANT_SERVICE_TOKEN", "")
BASE = "http://localhost:8004"

FLOWS = [
    {
        "flow_id": "book_repair",
        "tenant_id": "bike-shop",
        "trigger": "caller wants to book a repair or service appointment",
        "collect": [
            {"name": "customer_name", "prompt": "their name"},
            {"name": "phone", "prompt": "a callback number", "format": "phone"},
            {"name": "bike_type", "prompt": "what kind of bike it is",
             "options": ["road", "mountain", "e-bike"]},
            {"name": "problem", "prompt": "what's wrong with it"},
            {"name": "preferred_day", "prompt": "which day suits them", "format": "date"},
        ],
        "confirm": "So that's a {bike_type} - {problem} - for {customer_name} on {preferred_day}, callback {phone}. Have I got that right?",
        "action": {"connector": "booking", "operation": "create_booking"},
        "on_success": "You're booked in for {preferred_day}. We'll call {phone} if anything changes.",
        "on_failure": "I couldn't get that booked just now. Let me put you through to someone.",
    },
    {
        "flow_id": "check_status",
        "tenant_id": "bike-shop",
        "trigger": "caller wants to check the status of a repair already booked",
        "collect": [
            {"name": "phone", "prompt": "the number the booking was made under", "format": "phone"},
        ],
        "action": {"connector": "booking", "operation": "get_booking_status"},
        "on_success": "Let me check that for you.",
    },
    {
        "flow_id": "book_appointment",
        "tenant_id": "dental-clinic",
        "trigger": "caller wants to book, reschedule, or cancel a dental appointment",
        "collect": [
            {"name": "patient_name", "prompt": "their full name"},
            {"name": "phone", "prompt": "a contact number", "format": "phone"},
            {"name": "is_new_patient", "prompt": "whether they've been here before",
             "options": ["new", "returning"]},
            {"name": "preferred_day", "prompt": "which day works for them", "format": "date"},
        ],
        "confirm": "That's {patient_name}, {is_new_patient} patient, on {preferred_day}, contact {phone}. Correct?",
        "action": {"connector": "booking", "operation": "create_booking"},
        "on_success": "You're all set for {preferred_day}. See you then!",
    },
]

if __name__ == "__main__":
    for flow in FLOWS:
        r = requests.put(f"{BASE}/flows/{flow['flow_id']}?token={TOKEN}", json=flow)
        print(("Saved: " if r.ok else f"FAILED ({r.status_code}): ") + flow["flow_id"])
    for tid in ("bike-shop", "dental-clinic"):
        r = requests.get(f"{BASE}/tenants/{tid}/flows?token={TOKEN}")
        if r.ok:
            print(f"\n{tid}:", [f["flow_id"] for f in r.json()["flows"]])
