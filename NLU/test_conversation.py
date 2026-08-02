"""
Quick test: has a short multi-turn conversation with the NLU Service so you
can see it actually remembering context within one "call."

Run the service first:
    uvicorn nlu_service:app --reload --port 8002

Then:
    python test_conversation.py
"""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("NLU_SERVICE_TOKEN", "")
SERVICE_URL = "http://localhost:8002/reply"

# Simulates what the Orchestrator will do: keep appending turns to one
# growing history, exactly like a real call would.
conversation_history = []


def say(user_text):
    conversation_history.append({"role": "user", "content": user_text})
    print(f"You: {user_text}")

    resp = requests.post(SERVICE_URL, json={
        "token": TOKEN,
        "conversation_history": conversation_history,
    })
    resp.raise_for_status()
    reply_text = resp.json()["reply"]

    conversation_history.append({"role": "assistant", "content": reply_text})
    print(f"Bot: {reply_text}\n")


if __name__ == "__main__":
    say("Hi, do you have any appointments open tomorrow afternoon?")
    say("What about the day after instead?")
    say("Okay, what was the first day you said again?")  # tests real memory
