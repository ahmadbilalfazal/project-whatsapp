def test_register_and_login(client):
    rv = client.post('/auth/register', data={
        'username': 'u1',
        'email': 'u1@example.com',
        'business_name': 'Demo Business',
        'whatsapp_number': 'whatsapp:+923001234567',
        'city': 'Lahore',
        'country': 'Pakistan',
        'password': 'secret',
        'password2': 'secret'
    }, follow_redirects=True)
    assert b'registered user' in rv.data or b'Register' not in rv.data

    rv = client.post('/auth/login', data={
        'username': 'u1',
        'password': 'secret'
    }, follow_redirects=True)
    assert b'Business Dashboard' in rv.data
