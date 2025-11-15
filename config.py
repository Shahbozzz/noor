"""
Application configuration
"""
import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

# ✅ ВАЖНО: Импортируем правильный Redis client для sessions (БЕЗ decode_responses)
from utils.redis_client import redis_client_session


class Config:
    """Base configuration"""
    
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_POOL_SIZE = 10
    SQLALCHEMY_MAX_OVERFLOW = 20
    SQLALCHEMY_POOL_RECYCLE = 3600

    # ✅ Flask-Session Configuration (используем redis_client_session!)
    SESSION_TYPE = 'redis'
    SESSION_REDIS = redis_client_session  # ← КЛЮЧЕВОЕ ИЗМЕНЕНИЕ!
    SESSION_PERMANENT = True
    SESSION_USE_SIGNER = True
    SESSION_KEY_PREFIX = 'inha_session:'
    PERMANENT_SESSION_LIFETIME = timedelta(days=3)

    # Session Security
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # File uploads
    UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Email
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True') == 'True'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False') == 'True'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')

    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # Logging
    LOG_FILE = "app.log"
    LOG_LEVEL = "INFO"

    # Security Headers
    SEND_FILE_MAX_AGE_DEFAULT = 31536000


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_ECHO = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True

    # Production paths
    UPLOAD_FOLDER = '/var/www/inha/uploads'
    LOG_FILE = '/var/log/inha/app.log'

    # Stricter settings
    SQLALCHEMY_ECHO = False
    PROPAGATE_EXCEPTIONS = True

    # Rate Limiting
    RATELIMIT_STORAGE_URL = os.getenv('REDIS_RATELIMIT_URL', 'redis://localhost:6379/1')
    RATELIMIT_DEFAULT = "200 per hour"


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'development')
    return config.get(env, config['default'])
