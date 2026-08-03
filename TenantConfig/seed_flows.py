"""
Example flows, including a branching graph, so the shape of a real flow is
concrete rather than abstract.

Run after seed_tenants.py, with the service running:
    python seed_flows.py
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.environ.get("TENANT_SERVICE_TOKEN", "")
BASE = "http://localhost:8004"

FLOWS = [
    # --- Branching graph: the path differs for new vs returning patients ---
    {
        "flow_id": "book_appointment",
        "tenant_id": "dental-clinic",
        "trigger": "caller wants to book a dental appointment",
        "start": "ask_type",
        "nodes": {
            "ask_type": {
                "type": "collect",
                "fields": [{"name": "patient_type",
                            "prompt": "whether they've been here before",
                            "options": ["new", "returning"]}],
                "next": "route",
            },
            "route": {
                "type": "branch",
                "branches": [
                    {"when": [{"field": "patient_type", "op": "eq", "value": "new"}],
                     "goto": "new_patient"},
                    {"goto": "returning_patient"},
                ],
            },
            "new_patient": {
                "type": "collect",
                "fields": [
                    {"name": "full_name", "prompt": "their full name"},
                    {"name": "phone", "prompt": "a contact number", "format": "phone"},
                    {"name": "insurer", "prompt": "their insurance provider, or none"},
                ],
                "next": "schedule",
            },
            "returning_patient": {
                "type": "collect",
                "fields": [{"name": "phone", "prompt": "the number on their file",
                            "format": "phone"}],
                "next": "schedule",
            },
            "schedule": {
                "type": "collect",
                "fields": [{"name": "preferred_day", "prompt": "which day suits them",
                            "format": "date"}],
                "confirm": "Booking you in for {preferred_day}, contact number {phone}. Have I got that right?",
                "next": "book",
            },
            "book": {
                "type": "action",
                "connector": "booking",
                "operation": "create_booking",
                "result_key": "booking_ref",
                "next": "confirmed",
                "on_error": "book_failed",
            },
            "confirmed": {
                "type": "say",
                "text": "You're all set for {preferred_day}. We'll send a reminder to {phone}.",
                "next": "anything_else",
            },
            "anything_else": {
                "type": "say",
                "text": "Is there anything else I can help with?",
                "next": "finish",
            },
            "book_failed": {
                "type": "handoff",
                "text": "I'm having trouble completing that booking. Let me put you through to someone.",
            },
            "finish": {"type": "end"},
        },
    },
    # --- Simple linear graph ---
    {
        "flow_id": "book_repair",
        "tenant_id": "bike-shop",
        "trigger": "caller wants to book a repair or service",
        "start": "details",
        "nodes": {
            "details": {
                "type": "collect",
                "fields": [
                    {"name": "customer_name", "prompt": "their name"},
                    {"name": "phone", "prompt": "a callback number", "format": "phone"},
                    {"name": "bike_type", "prompt": "what kind of bike",
                     "options": ["road", "mountain", "e-bike"]},
                    {"name": "problem", "prompt": "what's wrong with it"},
                ],
                "next": "urgency_check",
            },
            # Branching on what they said, not on a question we asked
            "urgency_check": {
                "type": "branch",
                "branches": [
                    {"when": [{"field": "problem", "op": "contains", "value": "brake"}],
                     "goto": "urgent"},
                    {"goto": "normal_scheduling"},
                ],
            },
            "urgent": {
                "type": "say",
                "text": "Brakes are a safety issue, so we'll prioritise that.",
                "next": "normal_scheduling",
            },
            "normal_scheduling": {
                "type": "collect",
                "fields": [{"name": "preferred_day", "prompt": "which day they can drop it in",
                            "format": "date"}],
                "confirm": "So that's a {bike_type} - {problem} - dropping in {preferred_day}, callback {phone}. Right?",
                "next": "create",
            },
            "create": {
                "type": "action",
                "connector": "booking",
                "operation": "create_booking",
                "result_key": "booking_ref",
                "next": "ok",
                "on_error": "failed",
            },
            "ok": {"type": "say", "text": "Booked in for {preferred_day}. See you then!", "next": "finish"},
            "failed": {"type": "handoff", "text": "I couldn't get that booked. Transferring you now."},
            "finish": {"type": "end"},
        },
    },
]

if __name__ == "__main__":
    for flow in FLOWS:
        r = requests.put(f"{BASE}/flows/{flow['flow_id']}?token={TOKEN}", json=flow)
        if r.ok:
            print(f"Saved: {flow['flow_id']}")
        else:
            print(f"FAILED {flow['flow_id']}: {r.status_code} {r.text}")

    for tid in ("bike-shop", "dental-clinic"):
        r = requests.get(f"{BASE}/tenants/{tid}/flows?token={TOKEN}")
        if r.ok:
            print(f"\n{tid}:", [f["flow_id"] for f in r.json()["flows"]])
