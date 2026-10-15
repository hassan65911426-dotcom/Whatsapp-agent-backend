
import os
import time
import threading
import requests
from flask import Flask, jsonify

app = Flask(__name__)

# API configuration
WHATSAPP_API = "https://api.whatsapp.com/agent/v1"
GROQ_API = "https://api.groq.com/openai/v1/chat/completions"

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv(
    "GROQ_MODEL", "llama-3.3-70b-versatile"
)

# Temporary memory for this running instance
_state_lock = threading.Lock()
_state = {"offset": 0}
_seen = set()


def headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }


def ask_omega(user_text):
    """Generate an OMEGA reply using Groq."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is missing")

    response = requests.post(
        GROQ_API,
        headers=headers(GROQ_API_KEY),
        json={
            "model": GROQ_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are OMEGA, a helpful AI assistant. "
                        "Reply naturally, accurately and concisely. "
                        "Do not claim to have performed actions "
                        "you have not actually performed."
                    )
                },
                {"role": "user", "content": user_text}
            ],
            "temperature": 0.7,
            "max_tokens": 700
        },
        timeout=45
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def send_whatsapp(user_id, message_text):
    """Send a text message through the WhatsApp Agent API."""
    if not WHATSAPP_TOKEN:
        raise RuntimeError("WHATSAPP_ACCESS_TOKEN is missing")

    response = requests.post(
        f"{WHATSAPP_API}/messages",
        headers=headers(WHATSAPP_TOKEN),
        json={
            "messaging_product": "whatsapp",
            "to": f"user:{user_id}",
            "type": "text",
            "text": {"body": message_text[:4000]}
        },
        timeout=20
    )
    response.raise_for_status()
    return response.json()


def extract_text(message):
    """Read an incoming text message."""
    text_data = message.get("text", "")

    if isinstance(text_data, dict):
        return text_data.get("body", "").strip()

    if isinstance(text_data, str):
        return text_data.strip()

    return ""


def process_message(message):
    user_id = message.get("from")
    text = extract_text(message)

    if not user_id or not text:
        return "skipped"

    reply = ask_omega(text)
    send_whatsapp(user_id, reply)
    return "replied"


@app.get("/")
def home():
    return jsonify({
        "app": "OMEGA WhatsApp Agent",
        "status": "online",
        "endpoints": ["/", "/health", "/poll"]
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "online",
        "whatsapp_token_configured": bool(WHATSAPP_TOKEN),
        "groq_key_configured": bool(GROQ_API_KEY)
    })


@app.get("/poll")
def poll():
    """Fetch updates and reply to incoming text messages."""
    if not WHATSAPP_TOKEN or not GROQ_API_KEY:
        return jsonify({
            "error": "Configure WHATSAPP_ACCESS_TOKEN and GROQ_API_KEY"
        }), 500

    try:
        with _state_lock:
            current_offset = _state["offset"]

        response = requests.get(
            f"{WHATSAPP_API}/updates",
            headers=headers(WHATSAPP_TOKEN),
            params={
                "offset": current_offset,
                "limit": 10,
                "timeout": 5
            },
            timeout=15
        )
        response.raise_for_status()
        data = response.json()

        messages = data.get("messages", [])
        next_offset = data.get("next_offset", current_offset)
        results = []

        for message in messages:
            message_id = str(
                message.get("id", message.get("message_id", ""))
            )

            if message_id and message_id in _seen:
                continue

            try:
                result = process_message(message)
                results.append(result)

                if message_id:
                    _seen.add(message_id)

            except Exception as error:
                app.logger.exception("Message processing failed")
                results.append({
                    "status": "error",
                    "detail": str(error)[:200]
                })

        with _state_lock:
            _state["offset"] = next_offset

        # Keep temporary duplicate tracking bounded.
        if len(_seen) > 2000:
            _seen.clear()

        return jsonify({
            "status": "ok",
            "received": len(messages),
            "results": results,
            "next_offset": next_offset
        })

    except requests.RequestException:
        app.logger.exception("WhatsApp API request failed")
        return jsonify({
            "error": "WhatsApp API request failed. Check API credentials."
        }), 502

    except Exception:
        app.logger.exception("Unexpected polling error")
        return jsonify({"error": "Unexpected server error"}), 500
