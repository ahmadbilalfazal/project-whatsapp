from app import db, login
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(128))
    business = db.relationship('Business', backref='owner', uselist=False, cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


@login.user_loader
def load_user(id):
    return User.query.get(int(id))


class Business(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    whatsapp_number = db.Column(db.String(64), unique=True, index=True, nullable=False)
    city = db.Column(db.String(80))
    country = db.Column(db.String(80), default='Pakistan')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    documents = db.relationship('Document', backref='business', lazy='dynamic', cascade='all, delete-orphan')
    conversations = db.relationship('Conversation', backref='business', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Business {self.name}>'


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False, index=True)
    filename = db.Column(db.String(256), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    chunks = db.relationship('Chunk', backref='document', lazy='dynamic')


class Chunk(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False, index=True)
    doc_id = db.Column(db.Integer, db.ForeignKey('document.id'))
    page = db.Column(db.Integer)
    text = db.Column(db.Text)
    vector_id = db.Column(db.Integer, unique=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'doc_id': self.doc_id, 'page': self.page, 'text': self.text, 'vector_id': self.vector_id}


class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False, index=True)
    sender_phone = db.Column(db.String(64), index=True, nullable=False)
    display_name = db.Column(db.String(120))
    status = db.Column(db.String(32), default='active')
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')
    __table_args__ = (
        db.UniqueConstraint('business_id', 'sender_phone', name='uq_conversation_business_sender'),
    )

    def __repr__(self):
        return f'<Conversation {self.sender_phone}>'


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False, index=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    direction = db.Column(db.String(16), nullable=False)
    body = db.Column(db.Text, nullable=False)
    raw_response = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f'<Message {self.direction} {self.id}>'
