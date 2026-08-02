"""
Creates two example tenants so you have something to test against, and so
the shape of a real config is concrete rather than abstract.

Run the service first:
    uvicorn tenant_service:app --reload --port 8004

Then:
    python seed_tenants.py
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("TENANT_SERVICE_TOKEN", "")
BASE_URL = "http://localhost:8004"

TENANTS = [
    {
        "tenant_id": "bike-shop",
        "business_name": "Omar's Bicycle Repair",
        "greeting": "Thanks for calling Omar's Bicycle Repair! How can I help you today?",
        "system_prompt_extra": (
            "You work for Omar's Bicycle Repair. We service road bikes, mountain bikes, "
            "and e-bikes. A basic tune-up is 3000 PKR and takes about two days. "
            "Full overhaul is 8000 PKR and takes a week. We do NOT sell new bikes - "
            "if someone asks to buy one, say so plainly and suggest they try a dealer. "
            "If you don't know something specific about a repair, say you'll have "
            "someone call them back rather than guessing."
        ),
        "capabilities": [
            "book a repair appointment",
            "check the status of an existing repair",
            "quote standard service prices",
            "give opening hours and location",
        ],
        "escalation_phone": "+92-300-1234567",
        "enabled_connectors": ["booking"],
        "business_hours": {
            "monday": "09:00-18:00",
            "tuesday": "09:00-18:00",
            "wednesday": "09:00-18:00",
            "thursday": "09:00-18:00",
            "friday": "09:00-13:00",
            "saturday": "10:00-16:00",
            "sunday": None,
            "timezone": "Asia/Karachi",
        },
    },
    {
        "tenant_id": "dental-clinic",
        "business_name": "Bright Smile Dental",
        "greeting": "Bright Smile Dental, how can I help you?",
        "system_prompt_extra": (
            "You are the receptionist for Bright Smile Dental. You can book, "
            "reschedule, and cancel appointments. You must NEVER give medical or "
            "dental advice, diagnose anything, or comment on symptoms - if a caller "
            "describes pain or a medical concern, tell them a dentist will need to "
            "assess it and offer to book them in or transfer them. If a caller "
            "describes a dental emergency, transfer them to a human immediately."
        ),
        "capabilities": [
            "book an appointment",
            "reschedule or cancel an appointment",
            "give opening hours and location",
            "explain what to bring to a first visit",
        ],
        "escalation_phone": "+92-300-7654321",
        "enabled_connectors": ["booking"],
        "business_hours": {
            "monday": "10:00-19:00",
            "tuesday": "10:00-19:00",
            "wednesday": "10:00-19:00",
            "thursday": "10:00-19:00",
            "friday": "10:00-19:00",
            "saturday": "11:00-15:00",
            "sunday": None,
            "timezone": "Asia/Karachi",
        },
    },
]


if __name__ == "__main__":
    for tenant in TENANTS:
        url = f"{BASE_URL}/tenants/{tenant['tenant_id']}?token={TOKEN}"
        resp = requests.put(url, json=tenant)
        if resp.ok:
            print(f"Saved: {tenant['tenant_id']} ({tenant['business_name']})")
        else:
            print(f"FAILED {tenant['tenant_id']}: {resp.status_code} {resp.text}")

    resp = requests.get(f"{BASE_URL}/tenants?token={TOKEN}")
    print("\nAll tenants now:", resp.json())
