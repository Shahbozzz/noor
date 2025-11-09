"""
Security utilities with Redis support and Password Reset
"""
import bcrypt
import secrets
from datetime import datetime, timedelta
from flask import session

# Try to import Redis, fallback to dict if not available
try:
    from utils.redis_client import (
        store_pending_user as redis_store_pending_user,
        get_pending_user as redis_get_pending_user,
        delete_pending_user as redis_delete_pending_user,
        test_redis_connection
    )
    USE_REDIS = test_redis_connection()
except ImportError:
    USE_REDIS = False
    print("⚠️  Redis not available, using in-memory storage")

# Rate limiting constants
MAX_ATTEMPTS = 3
LOCK_MINUTES = 15
MAX_LOGIN_ATTEMPTS = 5
LOCK_MINUTES_LOGIN = 5
TOKEN_EXPIRY_MINUTES = 15
RESET_TOKEN_EXPIRY_MINUTES = 30  # Password reset tokens valid for 30 min

# Fallback: In-memory storage (only if Redis unavailable)
PENDING_USERS = {}
RESET_TOKENS = {}  # For password reset tokens


def hash_password(password):
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password, hashed_password):
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


def generate_verification_token():
    """Generate a secure verification token"""
    return secrets.token_urlsafe(32)


def create_pending_user(email, hashed_password):
    """Store pending user registration"""
    token = generate_verification_token()

    if USE_REDIS:
        redis_store_pending_user(token, email, hashed_password, TOKEN_EXPIRY_MINUTES)
    else:
        cleanup_expired_tokens()
        expiry_time = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRY_MINUTES)
        PENDING_USERS[token] = {
            "email": email,
            "password": hashed_password,
            "expires": expiry_time.isoformat()
        }

    return token


def get_pending_user(token):
    """Retrieve pending user data"""
    if USE_REDIS:
        return redis_get_pending_user(token)
    else:
        cleanup_expired_tokens()
        user_data = PENDING_USERS.get(token)

        if not user_data:
            return None

        expires = datetime.fromisoformat(user_data["expires"])
        if datetime.utcnow() > expires:
            PENDING_USERS.pop(token, None)
            return None

        return user_data


def remove_pending_user(token):
    """Remove pending user after successful registration"""
    if USE_REDIS:
        redis_delete_pending_user(token)
    else:
        PENDING_USERS.pop(token, None)


def cleanup_expired_tokens():
    """Remove expired tokens (only for dict fallback)"""
    if USE_REDIS:
        return

    now = datetime.utcnow()

    # Clean pending users
    expired = [
        token for token, data in PENDING_USERS.items()
        if datetime.fromisoformat(data["expires"]) < now
    ]
    for token in expired:
        PENDING_USERS.pop(token, None)

    # Clean reset tokens
    expired_resets = [
        token for token, data in RESET_TOKENS.items()
        if datetime.fromisoformat(data["expires"]) < now
    ]
    for token in expired_resets:
        RESET_TOKENS.pop(token, None)


# ============== PASSWORD RESET FUNCTIONS ==============

def create_password_reset_token(email):
    """
    Create a password reset token for user

    Args:
        email (str): User email

    Returns:
        str: Reset token
    """
    token = generate_verification_token()
    expiry_time = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)

    if USE_REDIS:
        # Store in Redis
        from utils.redis_client import redis_client
        import json

        reset_data = {
            "email": email,
            "expires": expiry_time.isoformat()
        }

        key = f"reset_token:{token}"
        redis_client.setex(
            key,
            timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES),
            json.dumps(reset_data)
        )
    else:
        # Store in dict
        cleanup_expired_tokens()
        RESET_TOKENS[token] = {
            "email": email,
            "expires": expiry_time.isoformat()
        }

    return token


def get_reset_token_email(token):
    """
    Get email associated with reset token

    Args:
        token (str): Reset token

    Returns:
        str or None: Email if token valid, None otherwise
    """
    if USE_REDIS:
        from utils.redis_client import redis_client
        import json

        try:
            key = f"reset_token:{token}"
            data = redis_client.get(key)

            if data:
                reset_data = json.loads(data)
                return reset_data["email"]
            return None
        except Exception:
            return None
    else:
        cleanup_expired_tokens()
        reset_data = RESET_TOKENS.get(token)

        if not reset_data:
            return None

        expires = datetime.fromisoformat(reset_data["expires"])
        if datetime.utcnow() > expires:
            RESET_TOKENS.pop(token, None)
            return None

        return reset_data["email"]


def remove_reset_token(token):
    """
    Remove reset token after password is changed

    Args:
        token (str): Reset token
    """
    if USE_REDIS:
        from utils.redis_client import redis_client
        key = f"reset_token:{token}"
        redis_client.delete(key)
    else:
        RESET_TOKENS.pop(token, None)


# ============== RATE LIMITING ==============

def check_rate_limit(session_key, max_attempts, lock_minutes):
    """Check if user is rate limited"""
    now = datetime.utcnow()
    attempts = session.get(session_key, {'count': 0, 'blocked_until': None})

    if attempts['blocked_until']:
        blocked_until = datetime.fromisoformat(attempts['blocked_until'])
        if now < blocked_until:
            remaining = int((blocked_until - now).total_seconds() // 60)
            return True, remaining, attempts
        else:
            attempts = {'count': 0, 'blocked_until': None}

    return False, 0, attempts


def increment_attempts(session_key, attempts, max_attempts, lock_minutes):
    """Increment failed attempt counter"""
    now = datetime.utcnow()
    attempts['count'] += 1

    if attempts['count'] >= max_attempts:
        attempts['blocked_until'] = (now + timedelta(minutes=lock_minutes)).isoformat()
        session[session_key] = attempts
        return True, 0

    session[session_key] = attempts
    remaining = max_attempts - attempts['count']
    return False, remaining


def reset_attempts(session_key):
    """Reset failed attempt counter"""
    session.pop(session_key, None)


def perform_timing_safe_comparison():
    """Perform dummy bcrypt to prevent timing attacks"""
    bcrypt.checkpw(b"dummy_password", bcrypt.gensalt())