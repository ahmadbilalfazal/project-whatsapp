from app.ingest import ingest_file
from app.models import Business, User


def test_seeded_business_answers_customer_questions(client, app, tmp_path):
    business_a = Business(
        owner=User(username='lahore', email='lahore@example.com'),
        name='Lahore Grill House',
        whatsapp_number='whatsapp:+923001111111',
        city='Lahore',
        country='Pakistan',
    )
    business_b = Business(
        owner=User(username='karachi', email='karachi@example.com'),
        name='Karachi Craft Market',
        whatsapp_number='whatsapp:+923002222222',
        city='Karachi',
        country='Pakistan',
    )

    demo_file_a = tmp_path / 'lahore_grill_house.txt'
    demo_file_a.write_text('Lahore Grill House opens Monday to Thursday at 12:00 PM and delivers across Lahore.', encoding='utf-8')
    demo_file_b = tmp_path / 'karachi_craft_market.txt'
    demo_file_b.write_text('Karachi Craft Market is based in Clifton and offers cash on delivery in Karachi.', encoding='utf-8')

    with app.app_context():
        from app import db

        db.session.add(business_a.owner)
        db.session.add(business_a)
        db.session.add(business_b.owner)
        db.session.add(business_b)
        db.session.commit()

        with demo_file_a.open('rb') as fh:
            ingest_file(fh, demo_file_a.name, business_a.id)
        with demo_file_b.open('rb') as fh:
            ingest_file(fh, demo_file_b.name, business_b.id)

    rv = client.post('/webhook/twilio', data={
        'From': 'whatsapp:+15550000001',
        'To': 'whatsapp:+923001111111',
        'Body': 'What time do you open on weekdays?',
    })
    assert rv.status_code == 200

    assert b'12:00 pm' in rv.data.lower()

    rv = client.post('/webhook/twilio', data={
        'From': 'whatsapp:+15550000002',
        'To': 'whatsapp:+923002222222',
        'Body': 'Do you offer cash on delivery?',
    })
    assert rv.status_code == 200
    assert b'cash on delivery' in rv.data.lower()

    rv = client.post('/webhook/twilio', data={
        'From': 'whatsapp:+15550000003',
        'To': 'whatsapp:+923002222222',
        'Body': 'Where are you located?',
    })
    assert rv.status_code == 200
    assert b'clifton' in rv.data.lower()