import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-this-secret'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'uploads')
    BUSINESS_NAME = os.environ.get('BUSINESS_NAME') or 'AI-Powered WhatsApp Business Agent'
    WHATSAPP_PROVIDER = os.environ.get('WHATSAPP_PROVIDER') or 'meta'
    WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN') or ''
    WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN') or ''
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID') or ''
    WHATSAPP_GRAPH_VERSION = os.environ.get('WHATSAPP_GRAPH_VERSION') or 'v25.0'
