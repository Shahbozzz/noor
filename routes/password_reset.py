"""
Password reset routes: forgot password, reset password
"""
import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from sqlalchemy.exc import SQLAlchemyError

from database.db import db, User
from utils.validators import validate_email, validate_password, sanitize_email
from utils.security import (
    hash_password, create_password_reset_token, get_reset_token_email,
    remove_reset_token, check_rate_limit, increment_attempts,
    reset_attempts, MAX_ATTEMPTS, LOCK_MINUTES
)
from utils.email_utils import send_password_reset_email

# Create Blueprint
password_reset_bp = Blueprint('password_reset', __name__)


@password_reset_bp.route('/forgot_password', methods=['GET'])
def forgot_password():
    """Forgot password page"""
    if "user_id" in session:
        return redirect(url_for('pages.main_page'))
    return render_template('forgot_password.html')


@password_reset_bp.route('/forgot_password_submit', methods=['POST'])
def forgot_password_submit():
    """Process forgot password form"""
    try:
        email = sanitize_email(request.form.get('email', ''))

        if not email:
            flash("⚠️ Email is required.", "error")
            return redirect(url_for('password_reset.forgot_password'))

        is_blocked, remaining_minutes, attempts = check_rate_limit(
            'reset_attempts', MAX_ATTEMPTS, LOCK_MINUTES
        )

        if is_blocked:
            flash(f"🚫 Too many attempts. Try again in {remaining_minutes} minutes.", "error")
            return redirect(url_for('password_reset.forgot_password'))

        if not validate_email(email):
            is_blocked, remaining = increment_attempts(
                'reset_attempts', attempts, MAX_ATTEMPTS, LOCK_MINUTES
            )
            if is_blocked:
                flash(f"🚫 Too many failed attempts. Blocked for {LOCK_MINUTES} minutes.", "error")
            else:
                flash(f"❌ Invalid email format. Attempt {MAX_ATTEMPTS - remaining}/{MAX_ATTEMPTS}.", "error")
            return redirect(url_for('password_reset.forgot_password'))

        user = User.query.filter_by(email=email).first()

        if not user:
            # Security: don't reveal if user exists
            flash("✅ If this email is registered, you'll receive a reset link.", "success")
            return render_template("password_reset_sent.html")

        token = create_password_reset_token(email)
        send_password_reset_email(email, token)
        reset_attempts('reset_attempts')

        logging.info(f"Password reset requested for {email}")
        return render_template("password_reset_sent.html")

    except Exception as e:
        logging.error(f"[PASSWORD RESET ERROR] {e}")
        flash("⚠️ Unexpected error. Please try again.", "error")
        return redirect(url_for('password_reset.forgot_password'))


@password_reset_bp.route('/reset_password/<token>', methods=['GET'])
def reset_password(token):
    """Reset password page with token"""
    if "user_id" in session:
        return redirect(url_for('pages.main_page'))

    email = get_reset_token_email(token)

    if not email:
        flash("❌ Invalid or expired reset link.", "error")
        return redirect(url_for('password_reset.forgot_password'))

    return render_template('reset_password.html', token=token)


@password_reset_bp.route('/reset_password/<token>', methods=['POST'])
def reset_password_submit(token):
    """Process password reset"""
    try:
        email = get_reset_token_email(token)

        if not email:
            flash("❌ Invalid or expired reset link.", "error")
            return redirect(url_for('password_reset.forgot_password'))

        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not password or not confirm_password:
            flash("⚠️ All fields are required.", "error")
            return render_template('reset_password.html', token=token)

        if password != confirm_password:
            flash("❌ Passwords do not match!", "error")
            return render_template('reset_password.html', token=token)

        is_valid, error_msg = validate_password(password)
        if not is_valid:
            flash(f"❌ {error_msg}", "error")
            return render_template('reset_password.html', token=token)

        user = User.query.filter_by(email=email).first()
        if not user:
            flash("❌ User not found.", "error")
            return redirect(url_for('password_reset.forgot_password'))

        user.password = hash_password(password)
        db.session.commit()
        remove_reset_token(token)

        logging.info(f"Password reset successful for user {user.id}")
        flash("✅ Password reset successful! Please log in with your new password.", "success")
        return redirect(url_for('auth.login'))

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"[DB ERROR] {e}")
        flash("⚠️ Database error. Please try again.", "error")
        return render_template('reset_password.html', token=token)
    except Exception as e:
        logging.error(f"[UNEXPECTED ERROR] {e}")
        flash("⚠️ Unexpected error. Please try again.", "error")
        return render_template('reset_password.html', token=token)