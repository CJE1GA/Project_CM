"""Flask app exposing the FULL chatbot locally and through Meta webhooks."""

import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from flask import Flask, Response, jsonify, render_template, request, session, has_request_context

import bot

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)

_state_lock = threading.Lock()
_user_states = {}
_processed_event_ids = set()
_processed_event_ids_lock = threading.Lock()

_outbound_lock = threading.Lock()
_last_outbound_send = 0.0
_meta_rate_limited_until = 0.0
_meta_rate_lock = threading.Lock()

_PROCESS_STARTED_AT = time.time()
_webhook_workers = []
_outbound_retry_queue = {}
_outbound_retry_lock = threading.Lock()


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
    try:
        with urllib.request.urlopen(request_obj, timeout=15) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as error:
        error_body = error.read().decode("utf-8", errors="replace")
        app.logger.error("Meta Graph API returned HTTP %s: %s", error.code, error_body)

        is_application_limit = '"code":4' in error_body or '"code": 4' in error_body
        if error.code == 429 or is_application_limit:
            global _meta_rate_limited_until
            with _meta_rate_lock:
                pause_seconds = 3600 if is_application_limit else 300
                _meta_rate_limited_until = max(_meta_rate_limited_until, time.time() + pause_seconds)
            app.logger.warning("Meta paused outbound sends for %s seconds.", pause_seconds)

        return {"error": {"message": error_body, "http_status": error.code}}
    except urllib.error.URLError as error:
        app.logger.error("Meta Graph API connection error: %s", error.reason)
        return {"error": {"message": str(error.reason)}}


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

    global _last_outbound_send
    with _meta_rate_lock:
        rate_limited_until = _meta_rate_limited_until
    if rate_limited_until > time.time():
        app.logger.warning("Skipping Instagram send while Meta rate limit is active.")
        return {"skipped": True, "reason": "Meta application request limit active."}

    with _outbound_lock:
        wait_seconds = max(0.0, 1.0 - (time.time() - _last_outbound_send))
        if wait_seconds:
            time.sleep(wait_seconds)
        _last_outbound_send = time.time()

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
        result = None
        if message["type"] == "text":
            result = _send_instagram_message(recipient_id, {"text": message["content"]})
        elif message["type"] == "image":
            public_url = _absolute_public_url(message["url"])
            result = _send_instagram_message(
                recipient_id,
                {
                    "attachment": {
                        "type": "image",
                        "payload": {"url": public_url, "is_reusable": False},
                    }
                },
            )
        elif message["type"] == "link":
            result = _send_instagram_message(recipient_id, {"text": f"{message['label']}: {message['url']}"})

        if isinstance(result, dict) and (result.get("error") or result.get("skipped")):
            outbound_message = None
            if message["type"] == "text":
                outbound_message = {"text": message["content"]}
            elif message["type"] == "image":
                outbound_message = {
                    "attachment": {
                        "type": "image",
                        "payload": {"url": public_url, "is_reusable": False},
                    }
                }
            elif message["type"] == "link":
                outbound_message = {"text": f"{message['label']}: {message['url']}"}
            if outbound_message:
                _queue_outbound_retry(recipient_id, outbound_message)
            app.logger.warning("Stopping remaining Instagram reply messages: %s", result)
            break


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

    if not state.get("instagram_username"):
        bot.set_instagram_username(state, f"@ig_{sender_id}")

    reply = bot.handle_message(text, state)

    _send_instagram_reply(sender_id, reply)
    return True


def _iter_meta_events(payload: dict):
    for entry in payload.get("entry", []):
        for event in entry.get("messaging", []):
            yield event


def _public_base_url() -> str:
    base_url = (
        os.environ.get("META_PUBLIC_BASE_URL", "").strip()
        or os.environ.get("RENDER_EXTERNAL_URL", "").strip()
    )
    if not base_url and has_request_context():
        base_url = request.host_url

    base_url = base_url.rstrip("/")
    if base_url.startswith("http://") and "localhost" not in base_url and "127.0.0.1" not in base_url:
        base_url = "https://" + base_url[len("http://") :]
    return base_url


def _absolute_public_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url

    base_url = _public_base_url()
    if not base_url:
        return url
    return urllib.parse.urljoin(base_url + "/", url.lstrip("/"))


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
    queued = 0

    for entry in payload.get("entry", []):
        entry_timestamp = entry.get("time")
        if isinstance(entry_timestamp, (int, float)):
            entry_timestamp_seconds = entry_timestamp / 1000 if entry_timestamp > 10_000_000_000 else entry_timestamp
            if entry_timestamp_seconds < _PROCESS_STARTED_AT:
                app.logger.info("Ignoring webhook replay received before process restart.")
                continue

        for event in entry.get("messaging", []):
            event_timestamp = event.get("timestamp")
            if isinstance(event_timestamp, (int, float)):
                event_timestamp_seconds = event_timestamp / 1000 if event_timestamp > 10_000_000_000 else event_timestamp
                if event_timestamp_seconds < _PROCESS_STARTED_AT:
                    app.logger.info("Ignoring old Instagram event before process restart.")
                    continue

            event_id = str((event.get("message") or {}).get("mid") or "").strip()
            if not event_id:
                sender_id = str((event.get("sender") or {}).get("id") or "")
                event_timestamp = event.get("timestamp") or ""
                postback_payload = str((event.get("postback") or {}).get("payload") or "")
                event_id = "|".join((sender_id, str(event_timestamp), postback_payload)).strip("|")

            with _processed_event_ids_lock:
                if event_id in _processed_event_ids:
                    continue
                _processed_event_ids.add(event_id)
                if len(_processed_event_ids) > 5000:
                    _processed_event_ids.clear()

            worker = threading.Thread(target=_process_meta_event, args=(event,), daemon=True)
            worker.start()
            _webhook_workers.append(worker)
            if len(_webhook_workers) > 100:
                _webhook_workers[:] = [item for item in _webhook_workers if item.is_alive()]
            queued += 1

    return jsonify({"status": "ok", "queued": queued})


@app.get("/healthz")
def healthcheck():
    config = _meta_config()
    with _meta_rate_lock:
        rate_limit_remaining = max(0, int(_meta_rate_limited_until - time.time()))
    with _outbound_retry_lock:
        retry_queue_size = len(_outbound_retry_queue)
    return jsonify(
        {
            "status": "ok",
            "meta_configured": bool(config["verify_token"] and config["access_token"] and config["instagram_account_id"]),
            "meta_rate_limit_seconds_remaining": rate_limit_remaining,
            "outbound_retry_queue_size": retry_queue_size,
        }
    )


def _queue_outbound_retry(recipient_id: str, message: dict) -> None:
    key = recipient_id + "|" + json.dumps(message, sort_keys=True, ensure_ascii=False)
    with _outbound_retry_lock:
        existing = _outbound_retry_queue.get(key)
        if existing:
            existing["not_before"] = max(existing["not_before"], time.time() + 900)
            return
        _outbound_retry_queue[key] = {
            "recipient_id": recipient_id,
            "message": message,
            "attempts": 0,
            "not_before": time.time() + 900,
        }


def _retry_outbound_worker() -> None:
    while True:
        time.sleep(60)
        now = time.time()
        with _meta_rate_lock:
            if _meta_rate_limited_until > now:
                continue

        with _outbound_retry_lock:
            items = list(_outbound_retry_queue.items())

        for key, item in items:
            if item["not_before"] > now:
                continue
            if item["attempts"] >= 12:
                with _outbound_retry_lock:
                    _outbound_retry_queue.pop(key, None)
                continue

            item["attempts"] += 1
            result = _send_instagram_message(item["recipient_id"], item["message"])
            if isinstance(result, dict) and not result.get("error") and not result.get("skipped"):
                with _outbound_retry_lock:
                    _outbound_retry_queue.pop(key, None)
            else:
                item["not_before"] = time.time() + 900


_retry_thread = threading.Thread(target=_retry_outbound_worker, daemon=True, name="meta-outbound-retry")
_retry_thread.start()

if __name__ == "__main__":
    use_https = os.environ.get("FLASK_USE_HTTPS", "0").strip().lower() in {"1", "true", "yes", "on"}
    debug_enabled = os.environ.get("FLASK_DEBUG", "1").strip().lower() in {"1", "true", "yes", "on"}
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    ssl_context = "adhoc" if use_https else None
    app.run(host=host, port=port, debug=debug_enabled, ssl_context=ssl_context)
