"""
API endpoints for Profile Editing (UPDATED WITH NAME/SURNAME + PHOTO DELETE)
"""
from flask import Blueprint, jsonify, request, session
from werkzeug.utils import secure_filename
from database.db import db, Form
from api.helpers import check_api_auth
import os
import bleach
from PIL import Image
from datetime import datetime, timedelta
import re

profile_edit_api = Blueprint('profile_edit_api', __name__, url_prefix='/api/profile')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
UPLOAD_FOLDER = 'static/uploads'
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB


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
# Redis Daily Upload Tracking
# ----------------------------
def get_daily_upload_count(user_id):
    """Get user's upload count for today using Redis"""
    try:
        from main import redis_client
        today = datetime.now().strftime('%Y-%m-%d')
        redis_key = f"photo_uploads:{user_id}:{today}"
        count = redis_client.get(redis_key)
        return int(count) if count else 0
    except Exception:
        return 0


def increment_daily_upload_count(user_id):
    """Increment user's upload count for today (expires at midnight)"""
    try:
        from main import redis_client
        today = datetime.now().strftime('%Y-%m-%d')
        redis_key = f"photo_uploads:{user_id}:{today}"
        
        # Calculate seconds until midnight
        now = datetime.now()
        midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
        seconds_until_midnight = int((midnight - now).total_seconds())
        
        # Increment and set expiry
        pipe = redis_client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, seconds_until_midnight)
        pipe.execute()
        
        return get_daily_upload_count(user_id)
    except Exception:
        return 1


def get_default_photo_path(sex):
    """Get path to default photo based on gender"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_filename = 'male_iut.png' if sex.lower() == 'male' else 'female_iut.png'
    return os.path.join(base_dir, 'static', 'uploads', default_filename)


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
    """Upload new profile photo (max 3 per day)"""
    from main import limiter
    @limiter.limit("20 per hour")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            # ✅ Check daily upload limit (3 per day)
            upload_count = get_daily_upload_count(user.id)
            if upload_count >= 3:
                return jsonify({
                    'success': False, 
                    'error': 'Daily upload limit reached (3 per day)',
                    'limit_reached': True,
                    'uploads_today': upload_count
                }), 429

            if 'photo' not in request.files:
                return jsonify({'success': False, 'error': 'No file uploaded'}), 400

            file = request.files['photo']

            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400

            if not allowed_file(file.filename):
                return jsonify({'success': False, 'error': 'Invalid file type. Use PNG, JPG, JPEG, or WebP'}), 400

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

            # Generate unique filename for WebP
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = secure_filename(f"user_{user.id}_{timestamp}.webp")
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

            # Resize main image (max 800x800) and save as WebP
            img.thumbnail((800, 800), Image.Resampling.LANCZOS)
            img.save(filepath, 'WEBP', quality=85, optimize=True)

            # Create thumbnail (150x150) as WebP
            thumb_filename = f"user_{user.id}_{timestamp}_thumb.webp"
            thumb_filepath = os.path.join(upload_folder, thumb_filename)

            thumb = img.copy()
            thumb.thumbnail((150, 150), Image.Resampling.LANCZOS)
            thumb.save(thumb_filepath, 'WEBP', quality=80, optimize=True)

            #  Delete old photos (only if not default photos)
            if form.photo_path and form.photo_path != 'male_iut.png' and form.photo_path != 'female_iut.png':
                old_filepath = os.path.join(upload_folder, form.photo_path)
                if os.path.exists(old_filepath):
                    try:
                        os.remove(old_filepath)
                    except Exception:
                        pass

            if form.photo_thumb_path and form.photo_thumb_path != 'male_iut.png' and form.photo_thumb_path != 'female_iut.png':
                old_thumb_filepath = os.path.join(upload_folder, form.photo_thumb_path)
                if os.path.exists(old_thumb_filepath):
                    try:
                        os.remove(old_thumb_filepath)
                    except Exception:
                        pass

            # Update database with FILENAME ONLY (not full path)
            form.photo_path = filename
            form.photo_thumb_path = thumb_filename
            db.session.commit()
            clear_user_cache()

            # Increment daily upload count
            new_count = increment_daily_upload_count(user.id)

            return jsonify({
                'success': True,
                'message': 'Photo uploaded successfully!',
                'data': {
                    'photo_path': f"/uploads/{filename}",
                    'photo_thumb_path': f"/uploads/{thumb_filename}"
                },
                'uploads_today': new_count,
                'uploads_remaining': 3 - new_count
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Failed to upload photo'}), 500

    return _inner()

# ----------------------------
# Delete Photo
# ----------------------------
@profile_edit_api.route('/photo', methods=['DELETE'])
def delete_photo():
    """Delete profile photo and revert to default"""
    from main import limiter
    @limiter.limit("20 per hour")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            form = Form.query.filter_by(user_id=user.id, active=True).first()

            if not form:
                return jsonify({'success': False, 'error': 'Profile not found'}), 404

            #  Check if user has a custom photo (not default)
            has_custom_photo = False
            if form.photo_path:
                has_custom_photo = not form.photo_path.startswith(('male_iut', 'female_iut', 'default_male', 'default_female'))

            if not has_custom_photo:
                return jsonify({
                    'success': False,
                    'error': 'No custom photo to delete'
                }), 400

            upload_folder = get_upload_folder()

            #  Delete physical files
            if form.photo_path:
                photo_filepath = os.path.join(upload_folder, form.photo_path)
                if os.path.exists(photo_filepath):
                    try:
                        os.remove(photo_filepath)
                    except Exception as e:
                        print(f"Error deleting photo: {e}")

            if form.photo_thumb_path:
                thumb_filepath = os.path.join(upload_folder, form.photo_thumb_path)
                if os.path.exists(thumb_filepath):
                    try:
                        os.remove(thumb_filepath)
                    except Exception as e:
                        print(f"Error deleting thumbnail: {e}")

            # Revert to default WebP photos based on gender
            if form.sex.lower() == 'male':
                form.photo_path = 'default_male.webp'
                form.photo_thumb_path = 'default_male_thumb.webp'
            else:
                form.photo_path = 'default_female.webp'
                form.photo_thumb_path = 'default_female_thumb.webp'

            db.session.commit()
            clear_user_cache()

            return jsonify({
                'success': True,
                'message': 'Photo deleted successfully!',
                'data': {
                    'photo_path': f"/uploads/{form.photo_path}",
                    'photo_thumb_path': f"/uploads/{form.photo_thumb_path}",
                    'is_default': True
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Failed to delete photo'}), 500

    return _inner()
# ----------------------------
# Get Daily Upload Stats
# ----------------------------
# ----------------------------
# Get Daily Upload Stats
# ----------------------------
@profile_edit_api.route('/photo/stats', methods=['GET'])
def get_upload_stats():
    """Get current daily upload statistics"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        upload_count = get_daily_upload_count(user.id)

        # Check if user has custom photo
        form = Form.query.filter_by(user_id=user.id, active=True).first()
        has_custom_photo = False
        if form and form.photo_path:
            has_custom_photo = not form.photo_path.startswith(('male_iut', 'female_iut', 'default_male', 'default_female'))

        return jsonify({
            'success': True,
            'uploads_today': upload_count,
            'uploads_remaining': max(0, 3 - upload_count),
            'limit_reached': upload_count >= 3,
            'has_custom_photo': has_custom_photo
        })
    except Exception as e:
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
