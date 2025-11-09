"""
Authentication routes: login, register, email verification, logout
"""
import logging
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from sqlalchemy.exc import SQLAlchemyError

from database.db import db, User, Form
from utils.validators import validate_email, validate_password, sanitize_email
from utils.security import (
    hash_password, verify_password, create_pending_user, get_pending_user,
    remove_pending_user, check_rate_limit, increment_attempts, reset_attempts,
    perform_timing_safe_comparison, MAX_ATTEMPTS, LOCK_MINUTES,
    MAX_LOGIN_ATTEMPTS, LOCK_MINUTES_LOGIN, TOKEN_EXPIRY_MINUTES
)
from utils.email_utils import send_verification_email
from utils.redis_client import set_user_online  # ✅ НОВОЕ!
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET'])
def login():
    """Login page"""
    if "user_id" in session:
        user = User.query.get(session["user_id"])
        if not user:
            session.clear()
            return render_template('login.html')

        existing_form = Form.query.filter_by(user_id=session["user_id"], active=True).first()
        if existing_form:
            return render_template("home.html", form=existing_form)
        return render_template('form.html')

    return render_template('login.html')


@auth_bp.route('/verify_login', methods=['POST'])
def verify_login():
    """Process login form"""
    is_blocked, remaining_minutes, attempts = check_rate_limit(
        'login_attempts', MAX_LOGIN_ATTEMPTS, LOCK_MINUTES_LOGIN
    )

    if is_blocked:
        flash(f"🚫 Too many failed login attempts. Try again in {remaining_minutes} minutes.", "error")
        return redirect(url_for('auth.login'))

    email = sanitize_email(request.form.get('email', ''))
    password = request.form.get('password', '')

    if not email or not password:
        flash("⚠️ Email and password are required.", "error")
        return redirect(url_for('auth.login'))

    if not validate_email(email):
        flash("⚠️ Invalid email format.", "error")
        return redirect(url_for('auth.login'))

    user = User.query.filter_by(email=email).first()

    if not user:
        perform_timing_safe_comparison()
        flash("❌ Invalid email or password.", "error")
        is_blocked, remaining = increment_attempts(
            'login_attempts', attempts, MAX_LOGIN_ATTEMPTS, LOCK_MINUTES_LOGIN
        )
        if is_blocked:
            flash(f"🚫 Too many failed attempts. Blocked for {LOCK_MINUTES_LOGIN} minutes.", "error")
        return redirect(url_for('auth.login'))

    if not verify_password(password, user.password):
        flash("❌ Invalid email or password.", "error")
        is_blocked, remaining = increment_attempts(
            'login_attempts', attempts, MAX_LOGIN_ATTEMPTS, LOCK_MINUTES_LOGIN
        )
        if is_blocked:
            flash(f"🚫 Too many failed attempts. Blocked for {LOCK_MINUTES_LOGIN} minutes.", "error")
        else:
            flash(f"⚠️ {remaining} attempts remaining.", "warning")
        return redirect(url_for('auth.login'))

    reset_attempts('login_attempts')

    # ✅ Данные теперь автоматически идут в Redis, не в cookies!
    session.permanent = True
    session["user_id"] = user.id
    session["user_email"] = user.email

    # ✅ НОВОЕ: Отметить пользователя как online
    set_user_online(user.id)

    logging.info(f"Successful login for user {user.id}")
    flash("✅ Logged in successfully!", "success")

    return redirect(url_for('pages.home'))


@auth_bp.route('/register', methods=['GET'])
def register():
    """Registration page"""
    if "user_id" in session:
        user = User.query.get(session["user_id"])
        if not user:
            session.clear()
            return render_template('register.html')

        existing_form = Form.query.filter_by(user_id=session["user_id"], active=True).first()
        if existing_form:
            return render_template("home.html", form=existing_form)
        return render_template('form.html')

    return render_template('register.html')


@auth_bp.route('/verify', methods=['POST'])
def verify():
    """Process registration form and send verification email"""
    try:
        email = sanitize_email(request.form.get('email', ''))
        password = request.form.get('password', '')
        reset_password = request.form.get('reset_password', '')

        if not email or not password or not reset_password:
            flash("⚠️ All fields are required.", "error")
            return redirect(url_for('auth.register'))

        is_blocked, remaining_minutes, attempts = check_rate_limit(
            'bad_attempts', MAX_ATTEMPTS, LOCK_MINUTES
        )

        if is_blocked:
            flash(f"🚫 Too many attempts. Try again in {remaining_minutes} minutes.", "error")
            return redirect(url_for('auth.register'))

        if not validate_email(email):
            is_blocked, remaining = increment_attempts(
                'bad_attempts', attempts, MAX_ATTEMPTS, LOCK_MINUTES
            )
            if is_blocked:
                flash(f"🚫 Too many failed attempts. Blocked for {LOCK_MINUTES} minutes.", "error")
            else:
                flash(f"❌ Email must be @student.inha.uz. Attempt {MAX_ATTEMPTS - remaining}/{MAX_ATTEMPTS}.", "error")
            return redirect(url_for('auth.register'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("⚠️ This email is already registered. Please log in instead.", "error")
            return redirect(url_for('auth.login'))

        if password != reset_password:
            flash("❌ Passwords do not match!", "error")
            return redirect(url_for('auth.register'))

        is_valid, error_msg = validate_password(password)
        if not is_valid:
            flash(f"❌ {error_msg}", "error")
            return redirect(url_for('auth.register'))

        reset_attempts('bad_attempts')
        hashed_password = hash_password(password)
        token = create_pending_user(email, hashed_password)

        send_verification_email(email, token)
        flash(f"✅ Verification email sent! Check your inbox. Link expires in {TOKEN_EXPIRY_MINUTES} minutes.",
              "success")

        return render_template("verify.html")

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"[DB ERROR] {e}")
        flash("⚠️ Database error. Please try again.", "error")
        return redirect(url_for('auth.register'))
    except Exception as e:
        logging.error(f"[UNEXPECTED ERROR] {e}")
        flash("⚠️ Unexpected error. Please try again.", "error")
        return redirect(url_for('auth.register'))


@auth_bp.route('/confirm/<token>')
def confirm(token):
    """Confirm email and create user account"""
    try:
        user_data = get_pending_user(token)
        if not user_data:
            flash("❌ Invalid or expired token.", "error")
            return redirect(url_for("auth.register"))

        existing_user = User.query.filter_by(email=user_data["email"]).first()
        if existing_user:
            remove_pending_user(token)
            flash("⚠️ This email is already registered. Please log in.", "error")
            return redirect(url_for("auth.login"))

        new_user = User(email=user_data["email"], password=user_data["password"])
        db.session.add(new_user)
        db.session.commit()

        # ✅ Данные автоматически в Redis!
        session.permanent = True
        session["user_id"] = new_user.id
        session["user_email"] = new_user.email

        # ✅ НОВОЕ: Отметить как online
        set_user_online(new_user.id)

        remove_pending_user(token)

        logging.info(f"New user registered: {new_user.id}")
        flash("✅ Registration successful! Welcome!", "success")

        existing_form = Form.query.filter_by(user_id=new_user.id, active=True).first()
        if existing_form:
            return render_template("home.html", form=existing_form)

        return render_template("form.html")

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"[DB ERROR] {e}")
        flash("⚠️ Database error. Please try again.", "error")
        return redirect(url_for("auth.register"))
    except Exception as e:
        logging.error(f"[UNEXPECTED ERROR] {e}")
        flash("⚠️ Unexpected error. Please try again.", "error")
        return redirect(url_for("auth.register"))


@auth_bp.route('/logout')
def logout():
    """Log out user"""
    user_id = session.get("user_id")

    # ✅ НОВОЕ: Удалить кеш пользователя при logout
    if user_id:
        from utils.redis_client import invalidate_user_cache
        invalidate_user_cache(user_id)
        logging.info(f"User {user_id} logged out")

    session.clear()  # ✅ Теперь очищает Redis session, не cookies!

    flash("✅ Logged out successfully!", "success")
    return redirect(url_for('auth.login'))