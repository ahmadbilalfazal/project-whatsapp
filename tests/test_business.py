from app.ingest import ingest_file
from app.models import Business, Conversation, Message, User


def test_register_login_and_dashboard(client):
    rv = client.post('/auth/register', data={
        'username': 'u1',
        'email': 'u1@example.com',
        'business_name': 'Lahore Grill House',
        'whatsapp_number': 'whatsapp:+923001111111',
        'city': 'Lahore',
        'country': 'Pakistan',
        'password': 'secret',
        'password2': 'secret'
    }, follow_redirects=True)
    assert b'registered user' in rv.data or b'Create your business workspace' not in rv.data

    rv = client.post('/auth/login', data={
        'username': 'u1',
        'password': 'secret'
    }, follow_redirects=True)
    assert b'Business Dashboard' in rv.data


def test_whatsapp_webhook_records_conversation(client, app, monkeypatch):
    from app.main import routes as main_routes

    monkeypatch.setattr(main_routes, 'answer_question', lambda question, **kwargs: {
        'status': 'OK',
        'answer': 'Thanks, we are open until 8 PM.',
        'citations': []
    })

    with app.app_context():
        from app import db

        user = User(username='owner', email='owner@example.com')
        user.set_password('secret')
        business = Business(
            owner=user,
            name='Lahore Grill House',
            whatsapp_number='whatsapp:+923001111111',
            city='Lahore',
            country='Pakistan',
        )
        db.session.add(user)
        db.session.add(business)
        db.session.commit()
        business_id = business.id

    rv = client.post('/webhook/twilio', data={
        'From': 'whatsapp:+15551234567',
        'To': 'whatsapp:+923001111111',
        'Body': 'What time do you close?'
    })

    assert rv.status_code == 200
    assert b'Thanks, we are open until 8 PM.' in rv.data

    with app.app_context():
        conversation = Conversation.query.filter_by(business_id=business_id, sender_phone='whatsapp:+15551234567').first()
        assert conversation is not None
        assert Message.query.filter_by(conversation_id=conversation.id).count() == 2


def test_business_dashboards_do_not_share_documents(client, app, business_factory, tmp_path):
    _, alpha_business = business_factory(
        username='alpha',
        email='alpha@example.com',
        business_name='Alpha Foods',
        whatsapp_number='whatsapp:+923001000001',
        city='Lahore',
        country='Pakistan',
    )
    _, beta_business = business_factory(
        username='beta',
        email='beta@example.com',
        business_name='Beta Repairs',
        whatsapp_number='whatsapp:+923001000002',
        city='Islamabad',
        country='Pakistan',
    )

    alpha_doc = tmp_path / 'alpha.txt'
    alpha_doc.write_text('Alpha Foods delivers in Lahore and opens at 9 AM.', encoding='utf-8')

    with app.app_context():
        with alpha_doc.open('rb') as fh:
            ingest_file(fh, alpha_doc.name, alpha_business.id)

    client.post('/auth/login', data={'username': 'alpha', 'password': 'secret'}, follow_redirects=True)
    rv = client.get('/', follow_redirects=True)
    assert b'Alpha Foods' in rv.data
    assert b'Beta Repairs' not in rv.data

    client.get('/auth/logout', follow_redirects=True)
    client.post('/auth/login', data={'username': 'beta', 'password': 'secret'}, follow_redirects=True)
    rv = client.get('/', follow_redirects=True)
    assert b'Alpha Foods' not in rv.data
    assert b'Beta Repairs' in rv.data