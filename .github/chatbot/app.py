"""Flask app exposing the FULL chatbot locally and through Meta webhooks."""

import json
import os
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, Response, jsonify, render_template, request, session

import bot

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

_state_lock = threading.Lock()
_user_states = {}


def _meta_config() -> dict:
    return {
        "verify_token": os.environ.get("META_VERIFY_TOKEN", ""),
        "access_token": os.environ.get("META_PAGE_ACCESS_TOKEN", ""),
        "instagram_account_id": os.environ.get("META_INSTAGRAM_ACCOUNT_ID", ""),
        "api_version": os.environ.get("META_GRAPH_API_VERSION", "v21.0"),
    }


def _graph_url(path: str, query: dict | None = None) -> str:
    config = _meta_config()
    clean_path = path.lstrip("/")
    url = f"https://graph.facebook.com/{config['api_version']}/{clean_path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    return url


def _graph_request(path: str, *, method: str = "GET", query: dict | None = None, body: dict | None = None):
    headers = {}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request_obj = urllib.request.Request(_graph_url(path, query), data=data, headers=headers, method=method)
    with urllib.request.urlopen(request_obj, timeout=15) as response:
        payload = response.read().decode("utf-8")
    return json.loads(payload) if payload else {}


def _get_user_state(user_key: str) -> dict:
    with _state_lock:
        if user_key not in _user_states:
            _user_states[user_key] = bot.new_state()
        return _user_states[user_key]


def _set_local_identity(state: dict, instagram_username: str) -> None:
    if isinstance(instagram_username, str):
        bot.set_instagram_username(state, instagram_username)
        bot.set_lead_identifier(state, bot.normalize_identifier(instagram_username) or instagram_username.strip())


def _fetch_instagram_username(sender_id: str) -> str:
    config = _meta_config()
    if not sender_id or not config["access_token"]:
        return ""

    try:
        payload = _graph_request(
            sender_id,
            query={
                "fields": "username,name",
                "access_token": config["access_token"],
            },
        )
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return ""

    username = payload.get("username") or payload.get("name") or ""
    if not isinstance(username, str):
        return ""
    username = username.strip()
    if not username:
        return ""
    return username if username.startswith("@") else f"@{username}"


def _send_instagram_message(recipient_id: str, message: dict) -> dict:
    config = _meta_config()
    if not config["access_token"] or not config["instagram_account_id"]:
        return {"skipped": True, "reason": "Missing Meta API credentials."}

    body = {
        "recipient": {"id": recipient_id},
        "messaging_type": "RESPONSE",
        "message": message,
    }
    return _graph_request(
        f"{config['instagram_account_id']}/messages",
        method="POST",
        query={"access_token": config["access_token"]},
        body=body,
    )


def _send_instagram_reply(recipient_id: str, reply: dict) -> None:
    for message in reply.get("messages", []):
        if message["type"] == "text":
            _send_instagram_message(recipient_id, {"text": message["content"]})
        elif message["type"] == "image":
            _send_instagram_message(
                recipient_id,
                {
                    "attachment": {
                        "type": "image",
                        "payload": {"url": message["url"], "is_reusable": False},
                    }
                },
            )
        elif message["type"] == "link":
            _send_instagram_message(recipient_id, {"text": f"{message['label']}: {message['url']}"})


def _extract_incoming_text(event: dict) -> tuple[str, str, list | None]:
    if event.get("postback"):
        postback = event["postback"]
        text = postback.get("title") or postback.get("payload") or ""
        return text, "postback", None

    message = event.get("message") or {}
    text = message.get("text", "")
    attachments = message.get("attachments")
    event_type = "text"
    if attachments:
        first_attachment = attachments[0] or {}
        event_type = first_attachment.get("type") or "attachment"
    return text, event_type, attachments


def _process_meta_event(event: dict) -> bool:
    sender_id = str((event.get("sender") or {}).get("id") or "").strip()
    if not sender_id:
        return False

    text, event_type, attachments = _extract_incoming_text(event)
    if bot.should_ignore(text, event_type, attachments):
        return False

    state = _get_user_state(sender_id)
    bot.set_lead_identifier(state, f"ig:{sender_id}")

    username = _fetch_instagram_username(sender_id)
    if username:
        bot.set_instagram_username(state, username)
    elif not state.get("instagram_username"):
        bot.set_instagram_username(state, f"@ig_{sender_id}")

    reply = bot.handle_message(text, state)
    _send_instagram_reply(sender_id, reply)
    return True


def _iter_meta_events(payload: dict):
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            yield event


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/start")
def start():
    payload = request.get_json(silent=True) or {}
    instagram_username = payload.get("instagram_username", "")
    state = bot.new_state()
    _set_local_identity(state, instagram_username)
    session["state"] = state
    return jsonify({"messages": [], "quick_replies": []})


@app.post("/api/message")
def message():
    payload = request.get_json(silent=True) or {}
    text = payload.get("message", "")
    event_type = payload.get("type", "text")
    attachments = payload.get("attachments")
    instagram_username = payload.get("instagram_username", "")
    if not isinstance(text, str) or len(text) > 500:
        return jsonify({"error": "Invalid message"}), 400

    if bot.should_ignore(text, event_type, attachments):
        return jsonify({"messages": [], "quick_replies": [], "ignored": True})

    state = session.get("state") or bot.new_state()
    _set_local_identity(state, instagram_username)
    reply = bot.handle_message(text, state)
    session["state"] = state
    return jsonify(reply)


@app.get("/webhook")
def verify_webhook():
    config = _meta_config()
    mode = request.args.get("hub.mode", "")
    verify_token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")

    if mode == "subscribe" and verify_token and verify_token == config["verify_token"]:
        return Response(challenge, status=200, mimetype="text/plain")
    return jsonify({"error": "Invalid webhook verification."}), 403


@app.post("/webhook")
def receive_webhook():
    payload = request.get_json(silent=True) or {}
    processed = 0
    for event in _iter_meta_events(payload):
        processed += int(_process_meta_event(event))
    return jsonify({"status": "ok", "processed": processed})


@app.get("/healthz")
def healthcheck():
    config = _meta_config()
    return jsonify(
        {
            "status": "ok",
            "meta_configured": bool(config["verify_token"] and config["access_token"] and config["instagram_account_id"]),
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
