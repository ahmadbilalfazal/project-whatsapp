import json
from datetime import datetime

import os
from flask import render_template, request, abort
from flask_login import login_required
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
from app.main import bp
from app import db
from app.models import Business, Chunk, Conversation, Document, Message
from app.rag import answer_question
from app.forms import QuestionTestForm
from app.whatsapp import (
    business_number_matches,
    meta_configured,
    meta_verify_challenge,
    parse_meta_payload,
    send_meta_reply,
    storage_whatsapp_number,
)


def _current_business():
    from flask_login import current_user
    return getattr(current_user, 'business', None)


def _business_for_whatsapp_number(number):
    if not number:
        return Business.query.first()
    for business in Business.query.all():
        if business_number_matches(business.whatsapp_number, number):
            return business
    return Business.query.first()


def _save_inbound_and_reply(business, sender, body, recipient=None, send_mode='twilio'):
    conversation = Conversation.query.filter_by(business_id=business.id, sender_phone=sender).first()
    if conversation is None:
        conversation = Conversation(business_id=business.id, sender_phone=sender, display_name=sender)
        db.session.add(conversation)
        db.session.flush()

    db.session.add(Message(business_id=business.id, conversation=conversation, direction='inbound', body=body))

    res = answer_question(body, business_id=business.id)
    db.session.add(Message(business_id=business.id, conversation=conversation, direction='outbound', body=res['answer'], raw_response=json.dumps(res)))
    conversation.last_message_at = datetime.utcnow()
    conversation.status = res.get('status', 'active')
    db.session.commit()

    if send_mode == 'meta' and recipient:
        send_meta_reply(recipient, res['answer'])

    return res


@bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    business = _current_business()
    test_form = QuestionTestForm()
    question_result = None
    if business is None:
        stats = {'documents': 0, 'chunks': 0, 'conversations': 0, 'messages': 0}
        return render_template('index.html', stats=stats, documents=[], conversations=[], recent_messages=[], business=None, test_form=test_form, question_result=question_result)

    if test_form.validate_on_submit():
        question_result = answer_question(test_form.question.data, business_id=business.id)
    stats = {
        'documents': Document.query.filter_by(business_id=business.id).count(),
        'chunks': Chunk.query.filter_by(business_id=business.id).count(),
        'conversations': Conversation.query.filter_by(business_id=business.id).count(),
        'messages': Message.query.filter_by(business_id=business.id).count(),
    }
    documents = Document.query.filter_by(business_id=business.id).order_by(Document.uploaded_at.desc()).all()
    conversations = Conversation.query.filter_by(business_id=business.id).order_by(Conversation.last_message_at.desc()).all()
    recent_messages = Message.query.filter_by(business_id=business.id).order_by(Message.created_at.desc()).limit(8).all()
    return render_template(
        'index.html',
        stats=stats,
        documents=documents,
        conversations=conversations,
        recent_messages=recent_messages,
        business=business,
        test_form=test_form,
        question_result=question_result,
    )


@bp.route('/conversations')
@login_required
def conversations():
    business = _current_business()
    if business is None:
        conversations = []
    else:
        conversations = Conversation.query.filter_by(business_id=business.id).order_by(Conversation.last_message_at.desc()).all()
    return render_template('conversations.html', conversations=conversations, business=business)


@bp.route('/conversations/<int:id>')
@login_required
def conversation_detail(id):
    conversation = Conversation.query.get_or_404(id)
    business = _current_business()
    if business is None or conversation.business_id != business.id:
        abort(404)
    messages = conversation.messages.order_by(Message.created_at.asc()).all()
    return render_template('conversation_detail.html', conversation=conversation, messages=messages, business=business)


@bp.route('/webhook/twilio', methods=['POST'])
def twilio_webhook():
    # Validate Twilio request signature if auth token is available
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    sig = request.headers.get('X-Twilio-Signature', '')
    if auth_token:
        validator = RequestValidator(auth_token)
        # For validation, Twilio expects the full URL and the POST params
        url = request.url
        params = request.form.to_dict() if request.form else {}
        if not validator.validate(url, params, sig):
            abort(403)

    sender = request.values.get('From') or request.values.get('from') or 'unknown'
    recipient = request.values.get('To') or request.values.get('to')
    business = _business_for_whatsapp_number(recipient)
    if business is None:
        return ('', 400)
    body = (request.values.get('Body') or request.values.get('body') or '').strip()
    if not body:
        return ('', 400)

    res = _save_inbound_and_reply(business, sender, body)

    twiml = MessagingResponse()
    twiml.message(res['answer'])
    return str(twiml), 200, {'Content-Type': 'application/xml'}


@bp.route('/webhook/whatsapp', methods=['GET', 'POST'])
def whatsapp_webhook():
    challenge = meta_verify_challenge(request.args)
    if challenge is not None:
        return challenge, 200

    if not meta_configured():
        return ('', 503)

    payload = request.get_json(silent=True) or {}
    message_payload = parse_meta_payload(payload)
    if not message_payload:
        return ('', 200)

    sender = message_payload['sender']
    recipient = message_payload['recipient']
    body = message_payload['body']

    business = _business_for_whatsapp_number(recipient)
    if business is None:
        return ('', 400)

    _save_inbound_and_reply(business, sender, body, recipient=sender, send_mode='meta')
    return ('', 200)
