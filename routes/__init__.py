"""
Routes package - all blueprints
"""

from .auth import auth_bp
from .password_reset import password_reset_bp
from .student_forms import forms_bp
from .pages import pages_bp

__all__ = ['auth_bp', 'password_reset_bp', 'forms_bp', 'pages_bp']