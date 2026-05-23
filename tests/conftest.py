import os
from pathlib import Path

import pytest
from app import create_app, db
from config import Config
from app.models import Business, User


os.environ.setdefault('RAG_MODEL', 'mock')


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    index_path = Path(__file__).resolve().parents[1] / 'faiss.index'
    if index_path.exists():
        index_path.unlink()
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def business_factory(app):
    def factory(
        username='u1',
        email='u1@example.com',
        business_name='Demo Business',
        whatsapp_number='whatsapp:+923001234567',
        city='Lahore',
        country='Pakistan',
        password='secret',
    ):
        user = User(username=username, email=email)
        user.set_password(password)
        business = Business(
            owner=user,
            name=business_name,
            whatsapp_number=whatsapp_number,
            city=city,
            country=country,
        )
        db.session.add(user)
        db.session.add(business)
        db.session.commit()
        return user, business

    return factory
