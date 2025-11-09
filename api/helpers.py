"""
Shared helper functions for API endpoints
"""
from flask import session
from database.db import User


def check_api_auth():
    """Check if user is authenticated for API access"""
    if "user_id" not in session:
        return None

    user = User.query.get(session["user_id"])
    if not user:
        session.clear()
        return None

    return user