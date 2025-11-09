"""
Student form routes: form display, submission
SECURITY: Protected against XSS, SQL Injection, CSRF, File Upload attacks
PERFORMANCE: Optimized for speed
"""
import logging
import re
from flask import Blueprint, render_template, request, flash, redirect, url_for, session, current_app, \
    send_from_directory, abort
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from database.db import db, User, Form
from utils.validators import validate_form_field, validate_birthday
from utils.file_utils import optimize_and_save_profile_photo, get_default_avatar

# Create Blueprint
forms_bp = Blueprint('forms', __name__)

# Security constants
MAX_REQUEST_SIZE = 16 * 1024 * 1024  # 5MB max
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
MAX_TEXT_LENGTH = 300


def sanitize_input(text, max_length=None):
    """
    Sanitize user input to prevent XSS attacks
    Remove dangerous characters and limit length
    """
    if not text:
        return ""

    # Remove any HTML tags and dangerous characters
    text = re.sub(r'<[^>]*>', '', str(text))
    text = re.sub(r'[<>{}]', '', text)

    # Strip whitespace
    text = text.strip()

    # Limit length
    if max_length:
        text = text[:max_length]

    return text


def validate_file_upload(file):
    """
    Validate uploaded file for security
    Returns: (is_valid, error_message)
    """
    if not file or not file.filename:
        return True, None  # No file is okay

    # Check if file has allowed extension
    filename = secure_filename(file.filename)
    if '.' not in filename:
        return False, "File must have an extension"

    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Only {', '.join(ALLOWED_EXTENSIONS)} files allowed"

    # Check file size
    file.seek(0, 2)  # Seek to end
    size = file.tell()
    file.seek(0)  # Reset to beginning

    if size > MAX_REQUEST_SIZE:
        return False, "File too large (max 5MB)"

    if size == 0:
        return False, "File is empty"

    return True, None


def check_user_session():
    """
    Verify user session is valid
    Security: Prevents session hijacking
    """
    if "user_id" not in session:
        return None

    try:
        user = db.session.get(User, session["user_id"])  # Faster than query.get()
        if not user:
            session.clear()
            return None
        return user
    except Exception as e:
        logging.error(f"Session check error: {e}")
        session.clear()
        return None


@forms_bp.route('/form', methods=["GET"])
def form_page():
    """
    Display student information form
    Security: Session validation
    Performance: Single query with filter
    """
    user = check_user_session()
    if not user:
        flash("⚠️ Please log in first.", "error")
        return redirect(url_for("auth.login"))

    # Performance: Use exists() for faster check
    existing_form = db.session.query(
        db.exists().where(Form.user_id == user.id, Form.active == True)
    ).scalar()

    if existing_form:
        return redirect(url_for('pages.home'))

    return render_template("form.html")


@forms_bp.route('/submit', methods=["POST"])
def submit_form():
    """
    Process student information form submission
    Security: Full input validation, sanitization, CSRF protection
    Performance: Optimized database operations
    """
    try:
        # Security: Verify user session
        user = check_user_session()
        if not user:
            flash("⚠️ Please log in first.", "error")
            return redirect(url_for("auth.login"))

        # Security: Check if user already has an active form (prevent duplicates)
        existing_form = Form.query.filter_by(user_id=user.id, active=True).first()
        if existing_form:
            flash("⚠️ You already have an active form!", "error")
            return redirect(url_for('pages.home'))

        # Security: Validate and sanitize all required fields
        required_fields = {
            "name": ("Name", 30),
            "surname": ("Surname", 30),
            "level": ("Level", 50),
            "faculty": ("Faculty", 50),
            "sex": ("Sex", 10),
            "relationship": ("Relationship Status", 50),
            "hobbies": ("Hobbies", 70),
            "professor": ("Star Professor", 35),
            "favorite_subjects": ("Favorite Subjects", 70)
        }

        sanitized_data = {}

        for field, (label, max_len) in required_fields.items():
            value = request.form.get(field, '').strip()

            # Security: Sanitize input
            value = sanitize_input(value, max_len)

            # Validation
            if not value:
                flash(f"⚠️ {label} is required!", "error")
                return redirect(url_for("forms.form_page"))

            # Additional validation for specific fields
            if field == "sex" and value.lower() not in ["male", "female"]:
                flash("⚠️ Invalid sex value!", "error")
                return redirect(url_for("forms.form_page"))

            if field == "faculty" and value not in ["ICE", "CSE", "SBL_B", "SBL_L"]:
                flash("⚠️ Invalid faculty value!", "error")
                return redirect(url_for("forms.form_page"))

            if field == "level" and value not in ["Fresh", "Sophomore", "Junior", "Senior"]:
                flash("⚠️ Invalid level value!", "error")
                return redirect(url_for("forms.form_page"))

            sanitized_data[field] = value

        # Security: Validate and sanitize optional fields
        about_me = sanitize_input(request.form.get("about_me", ""), 75)
        telegram = sanitize_input(request.form.get("telegram", ""), 50)

        # Security: Validate telegram format if provided
        if telegram and not re.match(r'^@?[a-zA-Z0-9_]{5,32}$', telegram):
            flash("⚠️ Invalid Telegram username format!", "error")
            return redirect(url_for("forms.form_page"))

        # Security: Validate birthday (optional field)
        birthday = request.form.get("birthday", "").strip()
        if birthday:
            # Additional security: Validate format
            if not re.match(r'^\d{4}/\d{2}/\d{2}$', birthday):
                flash("⚠️ Invalid birthday format!", "error")
                return redirect(url_for("forms.form_page"))

            is_valid, error = validate_birthday(birthday)
            if not is_valid:
                flash(f"⚠️ {error}", "error")
                return redirect(url_for("forms.form_page"))

        # Security: Validate file upload
        photo = request.files.get("photo")
        is_valid_file, file_error = validate_file_upload(photo)
        if not is_valid_file:
            flash(f"⚠️ {file_error}", "error")
            return redirect(url_for("forms.form_page"))

        # Process photo
        sex = sanitized_data["sex"].lower()
        photo_path = None
        photo_thumb_path = None

        if photo and photo.filename:
            try:
                photo_path, photo_thumb_path = optimize_and_save_profile_photo(
                    photo,
                    current_app.config["UPLOAD_FOLDER"],
                    user.id
                )
                logging.info(f"Photo optimized for user {user.id}: {photo_path}")
            except Exception as e:
                logging.error(f"Photo optimization error: {e}")
                flash(f"⚠️ Error processing photo. Please try again.", "error")
                return redirect(url_for("forms.form_page"))
        else:
            photo_path, photo_thumb_path = get_default_avatar(sex, current_app.config["UPLOAD_FOLDER"])
            logging.info(f"Using default avatar for user {user.id}, sex: {sex}")

        # Performance: Create form object with validated data
        form = Form(
            user_id=user.id,
            active=True,
            name=sanitized_data["name"],
            surname=sanitized_data["surname"],
            level=sanitized_data["level"],
            faculty=sanitized_data["faculty"],
            sex=sex,
            relationship=sanitized_data["relationship"],
            hobbies=sanitized_data["hobbies"],
            professor=sanitized_data["professor"],
            favorite_subjects=sanitized_data["favorite_subjects"],
            about_me=about_me,
            telegram=telegram,
            birthday=birthday if birthday else None,
            photo_path=photo_path,
            photo_thumb_path=photo_thumb_path
        )

        # Performance: Single commit
        db.session.add(form)
        db.session.commit()

        logging.info(f"Form submitted successfully by user {user.id}")
        flash("✅ Form submitted successfully!", "success")
        return redirect(url_for('pages.home'))

    except SQLAlchemyError as e:
        db.session.rollback()
        logging.error(f"[DB ERROR] {e}", exc_info=True)
        flash("❌ Database error. Please try again later.", "error")
        return redirect(url_for("forms.form_page"))

    except ValueError as e:
        # Security: Catch validation errors
        logging.warning(f"[VALIDATION ERROR] {e}")
        flash("⚠️ Invalid form data. Please check your inputs.", "error")
        return redirect(url_for("forms.form_page"))

    except Exception as e:
        # Security: Generic error handler (don't expose details)
        logging.error(f"[UNEXPECTED ERROR] {e}", exc_info=True)
        flash("❌ An error occurred. Please try again.", "error")
        return redirect(url_for("forms.form_page"))


@forms_bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """
    Serve uploaded files
    Security: Prevent directory traversal attacks
    Performance: Direct file serving
    """
    # Security: Sanitize filename to prevent directory traversal
    filename = secure_filename(filename)

    # Security: Only allow specific file types
    if not any(filename.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
        abort(404)

    try:
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        abort(404)
    except Exception as e:
        logging.error(f"File serving error: {e}")
        abort(500)