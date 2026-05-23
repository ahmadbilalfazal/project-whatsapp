from datetime import datetime, timedelta
from pathlib import Path
import json

from app import create_app, db
from app.ingest import ingest_file
from app.models import Business, Conversation, Document, Message, User


APP_DIR = Path(__file__).resolve().parent
DEMO_DIR = APP_DIR / 'demo_data' / 'pakistan'


def _reset_vector_store():
    index_path = APP_DIR / 'faiss.index'
    if index_path.exists():
        index_path.unlink()


DEMO_BUSINESSES = [
    {
        'username': 'lahoregrill',
        'email': 'lahoregrill@example.com',
        'business_name': 'Lahore Grill House',
        'whatsapp_number': 'whatsapp:+923001111111',
        'city': 'Lahore',
        'country': 'Pakistan',
        'files': ['lahore_grill_house_profile.txt', 'lahore_grill_house_menu.txt'],
        'conversations': [
            {
                'sender': 'whatsapp:+923110000001',
                'turns': [
                    ('inbound', 'Hi, are you guys open right now?'),
                    ('outbound', 'Yes, we’re open Monday to Thursday from 12:00 PM to 11:00 PM, and Friday to Sunday from 12:00 PM to 12:30 AM.'),
                    ('inbound', 'Nice. Do you deliver to DHA?'),
                    ('outbound', 'Yes, we deliver across Lahore, including DHA.'),
                    ('inbound', 'What about Garden Town?'),
                    ('outbound', 'Yes, Garden Town is covered too.'),
                    ('inbound', 'Perfect, thanks. Do you have cash on delivery?'),
                    ('outbound', 'Yes, cash on delivery is available.'),
                    ('inbound', 'Thanks, that helps a lot.'),
                    ('outbound', 'You’re welcome.'),
                ],
            },
            {
                'sender': 'whatsapp:+923110000002',
                'turns': [
                    ('inbound', 'Hello, I wanted to ask about your timings.'),
                    ('outbound', 'Of course — our weekday hours are 12:00 PM to 11:00 PM, and Friday through Sunday we stay open until 12:30 AM.'),
                    ('inbound', 'What time do you open on Fridays?'),
                    ('outbound', 'We open at 12:00 PM on Fridays.'),
                    ('inbound', 'And are you open on weekends too?'),
                    ('outbound', 'Yes, we’re open Saturday and Sunday too.'),
                    ('inbound', 'Okay great, thank you.'),
                    ('outbound', 'Anytime.'),
                ],
            },
        ],
    },
    {
        'username': 'karachicrafts',
        'email': 'karachicrafts@example.com',
        'business_name': 'Karachi Craft Market',
        'whatsapp_number': 'whatsapp:+923002222222',
        'city': 'Karachi',
        'country': 'Pakistan',
        'files': ['karachi_craft_market_profile.txt', 'karachi_craft_market_faq.txt'],
        'conversations': [
            {
                'sender': 'whatsapp:+923110000003',
                'turns': [
                    ('inbound', 'Hi, I’m checking if you deliver in Karachi.'),
                    ('outbound', 'Yes, we deliver in Karachi.'),
                    ('inbound', 'Do you offer COD?'),
                    ('outbound', 'Yes, cash on delivery is available in Karachi.'),
                    ('inbound', 'Great. Can I pay by bank transfer too?'),
                    ('outbound', 'Yes, we accept bank transfer, card payment, and cash on delivery.'),
                    ('inbound', 'Nice, and how long is delivery to Clifton?'),
                    ('outbound', 'Karachi delivery usually takes 1 to 2 business days.'),
                    ('inbound', 'Perfect, I’ll place an order soon.'),
                    ('outbound', 'Great — just send us a message when you’re ready.'),
                ],
            },
            {
                'sender': 'whatsapp:+923110000004',
                'turns': [
                    ('inbound', 'Assalam o Alaikum, where are you located?'),
                    ('outbound', 'We’re based in Clifton, Karachi.'),
                    ('inbound', 'Do you have a physical store in Clifton?'),
                    ('outbound', 'Yes, we’re in Clifton and support small artisans from Karachi and Hyderabad.'),
                    ('inbound', 'Can I visit today?'),
                    ('outbound', 'Yes, you’re welcome to visit during our daily hours from 10:00 AM to 8:00 PM.'),
                    ('inbound', 'Thanks for the info.'),
                    ('outbound', 'You’re welcome.'),
                ],
            },
        ],
    },
    {
        'username': 'islamabadtech',
        'email': 'islamabadtech@example.com',
        'business_name': 'Islamabad Tech Repair',
        'whatsapp_number': 'whatsapp:+923003333333',
        'city': 'Islamabad',
        'country': 'Pakistan',
        'files': ['islamabad_tech_repair_profile.txt', 'islamabad_tech_repair_services.txt'],
        'conversations': [
            {
                'sender': 'whatsapp:+923110000005',
                'turns': [
                    ('inbound', 'Hi, I dropped my phone and need help.'),
                    ('outbound', 'Sure — what device are you using?'),
                    ('inbound', 'Do you repair iPhone screens?'),
                    ('outbound', 'Yes, we do repair iPhone screens.'),
                    ('inbound', 'Nice. What about battery replacement?'),
                    ('outbound', 'Yes, we also handle Android battery replacement and other common repairs.'),
                    ('inbound', 'And do you fix laptops too?'),
                    ('outbound', 'Yes, we repair smartphones, laptops, tablets, and gaming consoles.'),
                    ('inbound', 'Alright, I’ll bring it in.'),
                    ('outbound', 'Sounds good — walk-ins are welcome.'),
                ],
            },
            {
                'sender': 'whatsapp:+923110000006',
                'turns': [
                    ('inbound', 'Hello, what are your service hours?'),
                    ('outbound', 'We’re open Monday to Saturday from 11:00 AM to 8:00 PM, and we’re closed on Sundays.'),
                    ('inbound', 'Are you open on Sundays?'),
                    ('outbound', 'No, we’re closed on Sundays.'),
                    ('inbound', 'Cool, thanks for confirming.'),
                    ('outbound', 'Anytime.'),
                ],
            },
        ],
    },
]


def _add_conversation(business, sender, turns, start_at):
    conversation = Conversation(
        business_id=business.id,
        sender_phone=sender,
        display_name=sender,
        status='active',
        last_message_at=start_at,
    )
    db.session.add(conversation)
    db.session.flush()

    current_time = start_at
    for direction, body in turns:
        message = Message(
            business_id=business.id,
            conversation_id=conversation.id,
            direction=direction,
            body=body,
            raw_response=json.dumps({'status': 'OK', 'answer': body, 'citations': []}) if direction == 'outbound' else None,
            created_at=current_time,
        )
        db.session.add(message)
        current_time += timedelta(minutes=1)

    conversation.last_message_at = current_time - timedelta(minutes=1)


def seed_demo_businesses():
    app = create_app()
    _reset_vector_store()

    with app.app_context():
        db.drop_all()
        db.create_all()

        now = datetime.utcnow() - timedelta(days=1)
        for business_index, config in enumerate(DEMO_BUSINESSES):
            user = User(username=config['username'], email=config['email'])
            user.set_password('password')
            business = Business(
                owner=user,
                name=config['business_name'],
                whatsapp_number=config['whatsapp_number'],
                city=config['city'],
                country=config['country'],
            )
            db.session.add(user)
            db.session.add(business)
            db.session.commit()

            for filename in config['files']:
                file_path = DEMO_DIR / filename
                with file_path.open('rb') as fh:
                    ingest_file(fh, filename, business.id)

            for convo_index, conversation in enumerate(config['conversations']):
                start_at = now + timedelta(hours=business_index * 4 + convo_index)
                _add_conversation(business, conversation['sender'], conversation['turns'], start_at)

        db.session.commit()

        for business in Business.query.order_by(Business.id).all():
            print(f'Seeded business: {business.name} ({business.city}, {business.country})')
            for conversation in business.conversations.order_by(Conversation.id).all():
                print(f'Conversation with {conversation.sender_phone}:')
                for message in conversation.messages.order_by(Message.created_at.asc()).all():
                    label = 'Q' if message.direction == 'inbound' else 'Webhook'
                    if message.direction == 'outbound':
                        body = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{message.body}</Message></Response>'
                    else:
                        body = message.body
                    print(f'  {label}: {body}')

        print(f'Documents: {Document.query.count()}, Conversations: {Conversation.query.count()}, Messages: {Message.query.count()}')


if __name__ == '__main__':
    seed_demo_businesses()
