"""
API endpoints for Profile Editing (UPDATED WITH NAME/SURNAME)
"""
from flask import Blueprint, jsonify, request, session
from werkzeug.utils import secure_filename
from database.db import db, Form
from api.helpers import check_api_auth
import os
import bleach
from PIL import Image
from datetime import datetime
import re

profile_edit_api = Blueprint('profile_edit_api', __name__, url_prefix='/api/profile')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
UPLOAD_FOLDER = 'static/uploads'
MAX_FILE_SIZE = 16 * 1024 * 1024  # 5MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_text(text, max_length=None):
    """Remove HTML/JS and trim whitespace"""
    text = bleach.clean(text, tags=[], strip=True).strip()
    if max_length and len(text) > max_length:
        text = text[:max_length]
    return text


def validate_single_word(text):
    """Check if text contains only one word (no spaces)"""
    return ' ' not in text.strip()


def clear_user_cache():
    """
    Clear user cache so it refreshes on next request
    This ensures navbar colors update immediately after profile changes
    """
    session.pop("user_cache", None)


def get_upload_folder():
    """Get absolute path to uploads folder"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_folder = os.path.join(base_dir, 'uploads')

    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder, exist_ok=True)

    return upload_folder


# ----------------------------
# Get Own Profile
# ----------------------------
@profile_edit_api.route('/me', methods=['GET'])
def get_my_profile():
    """Get current user's profile data"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        form = Form.query.filter_by(user_id=user.id, active=True).first()

        if not form:
            return jsonify({'success': False, 'error': 'Profile not found'}), 404

        return jsonify({
            'success': True,
            'profile': {
                'name': form.name,
                'surname': form.surname,
                'birthday': form.birthday,
                'level': form.level,
                'faculty': form.faculty,
                'favorite_subjects': form.favorite_subjects,
                'professor': form.professor,
                'relationship': form.relationship,
                'hobbies': form.hobbies,
                'telegram': form.telegram,
                'sex': form.sex,
                'photo_path': form.photo_path,
                'photo_thumb_path': form.photo_thumb_path
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ----------------------------
# Update Basic Info
# ----------------------------
@profile_edit_api.route('/basic', methods=['PATCH'])
def update_basic():
    """Update name, surname, birthday"""
    from main import limiter
    @limiter.limit("100 per minute")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            data = request.get_json()
            form = Form.query.filter_by(user_id=user.id, active=True).first()

            if not form:
                return jsonify({'success': False, 'error': 'Profile not found'}), 404

            if 'name' in data:
                name = sanitize_text(data['name'], 20)
                if not name or len(name) < 2:
                    return jsonify({'success': False, 'error': 'Name too short (min 2 characters)'}), 400
                if not validate_single_word(name):
                    return jsonify({'success': False, 'error': 'Name cannot contain spaces'}), 400
                form.name = name

            if 'surname' in data:
                surname = sanitize_text(data['surname'], 20)
                if not surname or len(surname) < 2:
                    return jsonify({'success': False, 'error': 'Surname too short (min 2 characters)'}), 400
                if not validate_single_word(surname):
                    return jsonify({'success': False, 'error': 'Surname cannot contain spaces'}), 400
                form.surname = surname

            if 'birthday' in data:
                birthday = sanitize_text(data['birthday'], 10)
                if birthday and len(birthday) >= 8:
                    form.birthday = birthday

            db.session.commit()
            clear_user_cache()

            return jsonify({
                'success': True,
                'message': 'Basic info updated',
                'data': {
                    'name': form.name,
                    'surname': form.surname,
                    'birthday': form.birthday
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return _inner()


# ----------------------------
# Update Academic Info
# ----------------------------
@profile_edit_api.route('/academic', methods=['PATCH'])
def update_academic():
    """Update level, faculty, subjects (max 50), professor (max 30)"""
    from main import limiter
    @limiter.limit("100 per minute")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            data = request.get_json()
            form = Form.query.filter_by(user_id=user.id, active=True).first()

            if not form:
                return jsonify({'success': False, 'error': 'Profile not found'}), 404

            if 'level' in data:
                level = data['level']
                valid_levels = ['Freshman', 'Sophomore', 'Junior', 'Senior']
                if level not in valid_levels:
                    return jsonify({'success': False, 'error': 'Invalid level'}), 400
                form.level = level

            if 'faculty' in data:
                faculty = data['faculty']
                valid_faculties = ['SBL_B', 'SBL_L', 'ICE', 'CSE']
                if faculty not in valid_faculties:
                    return jsonify({'success': False, 'error': 'Invalid faculty'}), 400
                form.faculty = faculty

            if 'favorite_subjects' in data:
                subjects = sanitize_text(data['favorite_subjects'], 50)
                form.favorite_subjects = subjects

            if 'professor' in data:
                professor = sanitize_text(data['professor'], 30)
                form.professor = professor

            db.session.commit()
            clear_user_cache()

            return jsonify({
                'success': True,
                'message': 'Academic info updated',
                'data': {
                    'level': form.level,
                    'faculty': form.faculty,
                    'favorite_subjects': form.favorite_subjects,
                    'professor': form.professor
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return _inner()


# ----------------------------
# Update Personal Info
# ----------------------------
@profile_edit_api.route('/personal', methods=['PATCH'])
def update_personal():
    """Update name, surname, relationship, hobbies (max 30)"""
    from main import limiter
    @limiter.limit("100 per minute")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            data = request.get_json()
            form = Form.query.filter_by(user_id=user.id, active=True).first()

            if not form:
                return jsonify({'success': False, 'error': 'Profile not found'}), 404

            if 'name' in data:
                name = sanitize_text(data['name'], 20)
                if not name or len(name) < 2:
                    return jsonify({'success': False, 'error': 'Name too short (min 2 characters)'}), 400
                if not validate_single_word(name):
                    return jsonify({'success': False, 'error': 'Name cannot contain spaces'}), 400
                form.name = name

            if 'surname' in data:
                surname = sanitize_text(data['surname'], 20)
                if not surname or len(surname) < 2:
                    return jsonify({'success': False, 'error': 'Surname too short (min 2 characters)'}), 400
                if not validate_single_word(surname):
                    return jsonify({'success': False, 'error': 'Surname cannot contain spaces'}), 400
                form.surname = surname

            if 'relationship' in data:
                relationship = sanitize_text(data['relationship'], 100)
                if not relationship:
                    return jsonify({'success': False, 'error': 'Relationship required'}), 400
                form.relationship = relationship

            if 'hobbies' in data:
                hobbies = sanitize_text(data['hobbies'], 30)
                if not hobbies:
                    return jsonify({'success': False, 'error': 'Hobbies required'}), 400
                form.hobbies = hobbies

            if 'birthday' in data:
                birthday = sanitize_text(data['birthday'], 10)
                if birthday and len(birthday) >= 8:
                    form.birthday = birthday

            db.session.commit()
            clear_user_cache()

            return jsonify({
                'success': True,
                'message': 'Personal info updated',
                'data': {
                    'name': form.name,
                    'surname': form.surname,
                    'relationship': form.relationship,
                    'hobbies': form.hobbies,
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return _inner()


# ----------------------------
# Update Contact (Telegram)
# ----------------------------
@profile_edit_api.route('/contact', methods=['PATCH'])
def update_contact():
    """Update telegram"""
    from main import limiter
    @limiter.limit("100 per minute")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            data = request.get_json()
            form = Form.query.filter_by(user_id=user.id, active=True).first()

            if not form:
                return jsonify({'success': False, 'error': 'Profile not found'}), 404

            if 'telegram' in data:
                telegram = sanitize_text(data['telegram'], 50)
                if telegram.startswith('@'):
                    telegram = telegram[1:]
                form.telegram = telegram if telegram else None

            db.session.commit()
            clear_user_cache()

            return jsonify({
                'success': True,
                'message': 'Contact updated',
                'data': {
                    'telegram': form.telegram
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return _inner()


# ----------------------------
# Update About Me
# ----------------------------
@profile_edit_api.route('/about', methods=['PATCH'])
def update_about():
    """Update about_me section (max 70)"""
    from main import limiter
    @limiter.limit("100 per minute")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            data = request.get_json()
            form = Form.query.filter_by(user_id=user.id, active=True).first()

            if not form:
                return jsonify({'success': False, 'error': 'Profile not found'}), 404

            if 'about_me' in data:
                about_me = sanitize_text(data['about_me'], 70)
                form.about_me = about_me if about_me else None

            db.session.commit()
            clear_user_cache()

            return jsonify({
                'success': True,
                'message': 'About me updated',
                'data': {
                    'about_me': form.about_me
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return _inner()


# ----------------------------
# Update Photo
# ----------------------------
@profile_edit_api.route('/photo', methods=['POST'])
def update_photo():
    """Upload new profile photo"""
    from main import limiter
    @limiter.limit("20 per hour")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            if 'photo' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'}), 400

            file = request.files['photo']

            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400

            if not allowed_file(file.filename):
                return jsonify({'success': False, 'error': 'Invalid file type'}), 400

            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)

            if file_size > MAX_FILE_SIZE:
                return jsonify({'success': False, 'error': f'File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB'}), 400

            form = Form.query.filter_by(user_id=user.id, active=True).first()

            if not form:
                return jsonify({'success': False, 'error': 'Profile not found'}), 404

            upload_folder = get_upload_folder()

            # Generate unique filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = secure_filename(f"user_{user.id}_{timestamp}.jpg")
            filepath = os.path.join(upload_folder, filename)

            # Save and process image
            img = Image.open(file)

            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background

            # Resize main image (max 800x800)
            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
            img.save(filepath, 'JPEG', quality=85, optimize=True)

            # Create thumbnail (150x150)
            thumb_filename = f"user_{user.id}_{timestamp}_thumb.jpg"
            thumb_filepath = os.path.join(upload_folder, thumb_filename)

            thumb = img.copy()
            thumb.thumbnail((150, 150), Image.Resampling.LANCZOS)
            thumb.save(thumb_filepath, 'JPEG', quality=80, optimize=True)

            # Delete old photos
            if form.photo_path and os.path.exists(form.photo_path):
                try:
                    os.remove(form.photo_path)
                except Exception:
                    pass

            if form.photo_thumb_path and os.path.exists(form.photo_thumb_path):
                try:
                    os.remove(form.photo_thumb_path)
                except Exception:
                    pass

            # Update database with full paths
            form.photo_path = filepath
            form.photo_thumb_path = thumb_filepath
            db.session.commit()
            clear_user_cache()

            return jsonify({
                'success': True,
                'message': 'Photo updated',
                'data': {
                    'photo_path': f"/uploads/{filename}",
                    'photo_thumb_path': f"/uploads/{thumb_filename}"
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return _inner()