import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-this-secret'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'uploads')
    BUSINESS_NAME = os.environ.get('BUSINESS_NAME') or 'AI-Powered WhatsApp Business Agent'
    WHATSAPP_PROVIDER = 'meta'
    WHATSAPP_VERIFY_TOKEN = 'my_verify_token_123'
    WHATSAPP_ACCESS_TOKEN = 'EAActaeRKzyABRgDn0BfCm4KtNdy1ySH7abVhq3J0S1GKZBpky9bmsFyGOBg4wYJE3Jf7obXmjq6ZBLId5RZCCc6bdt27sJIDTjO8umnzSmZB7YaCaFDZCRG52XINZCUiHuDzj0p0g5zQ4wnncdfZBnrRayxqd3kuF7ehJMDstVsJ30vjPg3fvD38QPOwZBQjyZCWveRVwo9I0XJnro944AINHZAwVLnZCy9BClTDp5OaLSElzA2RbxCZBO0JX9iDhLjK76iew70Kn1YIAz0oLeGNEjI1'
    WHATSAPP_PHONE_NUMBER_ID = '1047061318499457'
    WHATSAPP_GRAPH_VERSION = 'v25.0'
