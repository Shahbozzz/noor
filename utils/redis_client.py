"""
Redis client for handling temporary data storage and caching
"""
import os
import redis
import json
from datetime import timedelta

# Get Redis configuration from environment
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# ==========================================
# TWO SEPARATE REDIS CLIENTS
# ==========================================

# 1. For Flask-Session (needs bytes/pickle format)
redis_client_session = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=False  # ← ВАЖНО: False для Flask-Session!
)

# 2. For caching, rate limiting, etc 
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    decode_responses=True  # ← True для строк!
)


def test_redis_connection():
    """Test if Redis is connected"""
    try:
        redis_client.ping()
        return True
    except redis.ConnectionError:
        return False


# ==========================================
# REGISTRATION TOKEN FUNCTIONS
# ==========================================

def store_pending_user(token, email, hashed_password, expiry_minutes=15):
    """Store pending user registration in Redis"""
    try:
        user_data = {
            "email": email,
            "password": hashed_password
        }

        key = f"pending_user:{token}"
        redis_client.setex(
            key,
            timedelta(minutes=expiry_minutes),
            json.dumps(user_data)
        )
        return True
    except Exception as e:
        print(f"Redis store error: {e}")
        return False


def get_pending_user(token):
    """Retrieve pending user data from Redis"""
    try:
        key = f"pending_user:{token}"
        data = redis_client.get(key)

        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Redis get error: {e}")
        return None


def delete_pending_user(token):
    """Delete pending user after successful registration"""
    try:
        key = f"pending_user:{token}"
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Redis delete error: {e}")
        return False


# ==========================================
# RATE LIMITING FUNCTIONS
# ==========================================

def store_rate_limit(identifier, max_attempts, lock_minutes):
    """Store rate limiting data"""
    try:
        key = f"rate_limit:{identifier}"

        attempts = redis_client.get(key)
        if attempts is None:
            attempts = 0
        else:
            attempts = int(attempts)

        attempts += 1

        if attempts >= max_attempts:
            redis_client.setex(key, timedelta(minutes=lock_minutes), attempts)
            return True, 0

        redis_client.setex(key, timedelta(minutes=lock_minutes), attempts)
        remaining = max_attempts - attempts
        return False, remaining

    except Exception as e:
        print(f"Redis rate limit error: {e}")
        return False, max_attempts


def check_rate_limit(identifier):
    """Check if identifier is currently rate limited"""
    try:
        key = f"rate_limit:{identifier}"
        ttl = redis_client.ttl(key)

        if ttl > 0:
            return True, ttl
        return False, 0

    except Exception as e:
        print(f"Redis check error: {e}")
        return False, 0


def reset_rate_limit(identifier):
    """Reset rate limit counter"""
    try:
        key = f"rate_limit:{identifier}"
        redis_client.delete(key)
    except Exception as e:
        print(f"Redis reset error: {e}")


# ==========================================
# CACHING FUNCTIONS
# ==========================================

def cache_user_profile(user_id, profile_data, ttl_minutes=5):
    """
    Cache user profile data in Redis

    Args:
        user_id (int): User ID
        profile_data (dict): Profile data to cache
        ttl_minutes (int): Time to live in minutes
    """
    try:
        key = f"cache:student:{user_id}"
        redis_client.setex(
            key,
            timedelta(minutes=ttl_minutes),
            json.dumps(profile_data)
        )
        return True
    except Exception as e:
        print(f"Redis cache error: {e}")
        return False


def get_cached_user_profile(user_id):
    """
    Get cached user profile

    Args:
        user_id (int): User ID

    Returns:
        dict or None: Cached profile data or None
    """
    try:
        key = f"cache:student:{user_id}"
        data = redis_client.get(key)

        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Redis get cache error: {e}")
        return None


def invalidate_user_cache(user_id):
    """
    Invalidate (delete) user cache after profile update

    Args:
        user_id (int): User ID
    """
    try:
        key = f"cache:student:{user_id}"
        redis_client.delete(key)
        return True
    except Exception as e:
        print(f"Redis invalidate error: {e}")
        return False


def cache_friends_list(user_id, friends_data, ttl_minutes=10):
    """
    Cache user's friends list

    Args:
        user_id (int): User ID
        friends_data (list): List of friend IDs or data
        ttl_minutes (int): Time to live in minutes
    """
    try:
        key = f"cache:friends:{user_id}"
        redis_client.setex(
            key,
            timedelta(minutes=ttl_minutes),
            json.dumps(friends_data)
        )
        return True
    except Exception as e:
        print(f"Redis cache friends error: {e}")
        return False


def get_cached_friends(user_id):
    """Get cached friends list"""
    try:
        key = f"cache:friends:{user_id}"
        data = redis_client.get(key)

        if data:
            return json.loads(data)
        return None
    except Exception as e:
        print(f"Redis get friends error: {e}")
        return None


def invalidate_friends_cache(user_id):
    """Invalidate friends cache"""
    try:
        key = f"cache:friends:{user_id}"
        redis_client.delete(key)
        return True
    except Exception as e:
        return False


def set_user_online(user_id, ttl_minutes=5):
    """
    Mark user as online

    Args:
        user_id (int): User ID
        ttl_minutes (int): How long to keep online status
    """
    try:
        from datetime import datetime
        key = f"online:{user_id}"
        redis_client.setex(
            key,
            timedelta(minutes=ttl_minutes),
            datetime.now().isoformat()
        )
        return True
    except Exception as e:
        print(f"Redis online error: {e}")
        return False


def is_user_online(user_id):
    """Check if user is online"""
    try:
        key = f"online:{user_id}"
        return redis_client.exists(key) > 0
    except Exception as e:
        return False


def get_online_friends(friend_ids):
    """
    Get list of online friends from list of friend IDs

    Args:
        friend_ids (list): List of user IDs

    Returns:
        list: List of online user IDs
    """
    try:
        online = []
        for friend_id in friend_ids:
            if is_user_online(friend_id):
                online.append(friend_id)
        return online
    except Exception as e:
        print(f"Redis online friends error: {e}")
        return []


# Test connection on import
if not test_redis_connection():
    print("⚠️  WARNING: Redis is not connected! Using fallback in-memory storage.")
    print("   For production, make sure Redis is running.")
