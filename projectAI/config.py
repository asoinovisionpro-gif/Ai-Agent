import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///aidlms.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_BOOKING_DURATION_HOURS = int(os.environ.get('MAX_BOOKING_DURATION_HOURS', 4))
    DAILY_BOOKING_LIMIT = int(os.environ.get('DAILY_BOOKING_LIMIT', 2))
    ANTHROPIC_API_KEY = os.environ.get('CLAUDE_API_KEY', '')
    SOCKETIO_ASYNC_MODE = os.environ.get('SOCKETIO_ASYNC_MODE', 'threading')
    DECISION_AGENT_ESCALATION_THRESHOLD = os.environ.get('DECISION_AGENT_ESCALATION_THRESHOLD', 'HIGH')
