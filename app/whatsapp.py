import json
import os
import re
from urllib import error, request

from flask import current_app


def normalize_whatsapp_number(value):
    if not value:
        return ''
    text = str(value).strip()
    if text.startswith('whatsapp:'):
        text = text[len('whatsapp:'):]
    digits = re.sub(r'\D', '', text)
    if not digits:
        return text
    if text.startswith('+') or str(value).strip().startswith('whatsapp:+'):
        return f'+{digits}'
    return digits


def storage_whatsapp_number(value):
    normalized = normalize_whatsapp_number(value)
    if not normalized:
        return ''
    return f'whatsapp:{normalized}'


def business_number_matches(stored_number, incoming_number):
    return normalize_whatsapp_number(stored_number) == normalize_whatsapp_number(incoming_number)


def _setting(name, default=''):
    try:
        value = current_app.config.get(name, default)
    except RuntimeError:
        value = default
    if value in (None, ''):
        return os.environ.get(name, default)
    return value


def meta_configured():
    return bool(_setting('WHATSAPP_ACCESS_TOKEN') and _setting('WHATSAPP_PHONE_NUMBER_ID'))


def meta_verify_challenge(args):
    expected_token = _setting('WHATSAPP_VERIFY_TOKEN')
    if not expected_token:
        return None

    mode = args.get('hub.mode')
    token = args.get('hub.verify_token')
    challenge = args.get('hub.challenge')
    if mode == 'subscribe' and token == expected_token and challenge:
        return challenge
    return None


def parse_meta_payload(payload):
    for entry in payload.get('entry', []) if isinstance(payload, dict) else []:
        for change in entry.get('changes', []):
            value = change.get('value', {})
            messages = value.get('messages') or []
            if not messages:
                continue
            message = messages[0]
            sender = message.get('from') or ''
            body = (message.get('text') or {}).get('body') or ''
            recipient = (value.get('metadata') or {}).get('display_phone_number') or ''
            if sender and body:
                return {
                    'sender': storage_whatsapp_number(sender),
                    'recipient': storage_whatsapp_number(recipient),
                    'body': body.strip(),
                }
    return None


def send_meta_reply(to_number, body):
    if not meta_configured():
        return None

    phone_number_id = _setting('WHATSAPP_PHONE_NUMBER_ID')
    token = _setting('WHATSAPP_ACCESS_TOKEN')
    api_version = _setting('WHATSAPP_GRAPH_VERSION', 'v20.0')
    url = f'https://graph.facebook.com/{api_version}/{phone_number_id}/messages'
    payload = json.dumps({
        'messaging_product': 'whatsapp',
        'to': normalize_whatsapp_number(to_number),
        'type': 'text',
        'text': {'body': body},
    }).encode('utf-8')

    req = request.Request(
        url,
        data=payload,
        method='POST',
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
    )

    try:
        with request.urlopen(req, timeout=15) as response:
            raw = response.read().decode('utf-8')
            return json.loads(raw) if raw else {}
    except error.HTTPError as exc:
        detail = exc.read().decode('utf-8', errors='ignore')
        return {'error': f'HTTP {exc.code}', 'detail': detail}
    except Exception as exc:
        return {'error': str(exc)}