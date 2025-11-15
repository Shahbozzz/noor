"""
API endpoints for Student Voice (Quotes) with Faculty Separation
OPTIMIZED VERSION - Rate limiting only on WRITE operations
"""
from flask import Blueprint, jsonify, request, session, make_response
from sqlalchemy import func, or_
from database.db import db, VoicePost, VoiceLike, Notification, User, Form
from api.helpers import check_api_auth
import bleach
import re
import json
from datetime import datetime, timedelta, timezone

# Create API Blueprint
voice_api = Blueprint('voice_api', __name__, url_prefix='/api')

# Faculty mappings - YOUR EXACT DATABASE CODES
FACULTY_GROUPS = {
    'SOCIE': ['ICE', 'CSE'],
    'SBL': ['SBL_B', 'SBL_L']
}

def get_faculty_group(faculty):
    """Determine which group (SOCIE/SBL) a faculty belongs to"""
    if not faculty:
        return None

    faculty_clean = faculty.strip().upper()

    if faculty_clean in ['ICE', 'CSE']:
        return 'SOCIE'
    elif faculty_clean in ['SBL_B', 'SBL_L']:
        return 'SBL'

    for group, codes in FACULTY_GROUPS.items():
        for code in codes:
            if code in faculty_clean or faculty_clean in code:
                return group
    return None


# ----------------------------
# Helper functions
# ----------------------------

def sanitize_text(text):
    """Remove HTML/JS and trim whitespace"""
    text = bleach.clean(text, tags=[], strip=True)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def check_rate_limit():
    """Check cookie-based rate limit: 5 edits per hour"""
    cookie_name = 'voice_edits'
    edits_data = request.cookies.get(cookie_name)

    if not edits_data:
        return True, []

    try:
        edits = json.loads(edits_data)
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)

        recent_edits = [
            edit_time for edit_time in edits
            if datetime.fromisoformat(edit_time) > one_hour_ago
        ]

        if len(recent_edits) >= 5:
            return False, recent_edits

        return True, recent_edits
    except Exception:
        return True, []


def update_rate_limit_cookie(response, existing_edits):
    """Update rate limit cookie with new edit timestamp"""
    now = datetime.utcnow()
    one_hour_ago = now - timedelta(hours=1)

    recent_edits = [
        edit_time for edit_time in existing_edits
        if datetime.fromisoformat(edit_time) > one_hour_ago
    ]
    recent_edits.append(now.isoformat())

    response.set_cookie(
        'voice_edits',
        json.dumps(recent_edits),
        max_age=3600,
        httponly=True,
        secure=False,
        samesite='Lax'
    )
    return response


# ----------------------------
# Voice Routes
# ----------------------------

@voice_api.route('/voice/user-info', methods=['GET'])
def get_user_info():
    """Get current user's faculty information - NO RATE LIMIT (read-only)"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        user_form = Form.query.filter_by(user_id=user.id, active=True).first()

        if not user_form:
            return jsonify({'success': False, 'error': 'Profile not found'}), 400

        faculty_group = get_faculty_group(user_form.faculty)
        if not faculty_group:
            return jsonify({
                'success': False,
                'error': f'Invalid faculty: {user_form.faculty}. Expected: ICE, CSE, SBL_B, or SBL_L'
            }), 400

        return jsonify({
            'success': True,
            'user_id': user.id,
            'faculty': user_form.faculty,
            'faculty_group': faculty_group
        })

    except Exception:
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@voice_api.route('/voice', methods=['POST'])
def create_or_update_post():
    """Create or update user's voice post - RATE LIMITED (5 per hour via cookie)"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    user_form = Form.query.filter_by(user_id=user.id, active=True).first()
    if not user_form:
        return jsonify({'success': False, 'error': 'Profile not found'}), 400

    user_faculty_group = get_faculty_group(user_form.faculty)
    if not user_faculty_group:
        return jsonify({
            'success': False,
            'error': f'Invalid faculty: {user_form.faculty}'
        }), 400

    allowed, existing_edits = check_rate_limit()
    if not allowed:
        return jsonify({
            'success': False,
            'error': 'Rate limit exceeded. You can only edit 5 times per hour.',
            'retry_after': 3600
        }), 429

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        text = data.get('text', '').strip()
        target_faculty = data.get('faculty')

        if not text:
            return jsonify({'success': False, 'error': 'Text is required'}), 400

        if target_faculty != user_faculty_group:
            return jsonify({
                'success': False,
                'error': f'You can only post in {user_faculty_group} section'
            }), 403

        text = sanitize_text(text)

        if len(text) > 100:
            return jsonify({'success': False, 'error': 'Text exceeds 100 characters'}), 400

        existing_post = VoicePost.query.filter_by(
            user_id=user.id,
            faculty_group=user_faculty_group
        ).first()

        if existing_post:
            existing_post.text = text
            existing_post.likes_count = 0
            existing_post.updated_at = db.func.now()
            VoiceLike.query.filter_by(post_id=existing_post.id).delete()
            db.session.commit()
            response = make_response(jsonify({'success': True, 'message': 'Post updated'}))
            return update_rate_limit_cookie(response, existing_edits)

        new_post = VoicePost(
            user_id=user.id,
            text=text,
            faculty_group=user_faculty_group
        )
	
       	db.session.add(new_post)
        db.session.commit()

        response = make_response(jsonify({'success': True, 'message': 'Post created'}))
        return update_rate_limit_cookie(response, existing_edits)

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f'Database error: {str(e)}'}), 500


@voice_api.route('/voice', methods=['GET'])
def get_voice_feed():
    """Get voice posts feed - NO RATE LIMIT (read-only)"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        faculty_filter = request.args.get('faculty')
        sort = request.args.get('sort', 'most_liked')
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 30, type=int), 30)

        if faculty_filter not in ['SOCIE', 'SBL']:
            return jsonify({'success': False, 'error': 'Invalid faculty'}), 400

        query = VoicePost.query.filter_by(faculty_group=faculty_filter)

        if sort == 'random':
            query = query.order_by(func.random())
        else:
            query = query.order_by(
                VoicePost.likes_count.desc(),
                VoicePost.created_at.desc()
            )

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        posts = []
        for post in pagination.items:
            author_form = Form.query.filter_by(user_id=post.user_id, active=True).first()
            if not author_form:
                continue

            user_liked = VoiceLike.query.filter_by(
                post_id=post.id,
                user_id=user.id
            ).first() is not None

            posts.append({
                'id': post.id,
                'text': post.text,
                'likes_count': post.likes_count,
                'created_at': post.created_at.isoformat(),
                'user_liked': user_liked,
                'faculty_group': post.faculty_group,
                'author': {
                    'user_id': post.user_id,
                    'name': author_form.name,
                    'surname': author_form.surname,
                    'photo_thumb_path': author_form.photo_thumb_path,
                    'photo_path': author_form.photo_path,
                    'faculty': author_form.faculty
                }
            })

        return jsonify({
            'success': True,
            'posts': posts,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })

    except Exception:
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@voice_api.route('/voice/like', methods=['POST'])
def toggle_like():
    """Toggle like on a voice post - MODERATE RATE LIMIT"""
    from main import limiter

    @limiter.limit("100 per hour")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            data = request.get_json()
            post_id = data.get('post_id')
            if not post_id:
                return jsonify({'success': False, 'error': 'post_id required'}), 400

            post = VoicePost.query.get(post_id)
            if not post:
                return jsonify({'success': False, 'error': 'Post not found'}), 404

            existing_like = VoiceLike.query.filter_by(
                post_id=post_id,
                user_id=user.id
            ).first()

            if existing_like:
                db.session.delete(existing_like)
                post.likes_count = max(0, post.likes_count - 1)
                db.session.commit()
                return jsonify({
                    'success': True,
                    'liked': False,
                    'likes_count': post.likes_count
                })

            new_like = VoiceLike(post_id=post_id, user_id=user.id)
            db.session.add(new_like)
            post.likes_count += 1

            if post.user_id != user.id:
                liker_form = Form.query.filter_by(user_id=user.id, active=True).first()
                if liker_form:
                    notification = Notification(
                        user_id=post.user_id,
                        from_user_id=user.id,
                        type='voice_like',
                        post_id=post.id,
                        message=f"❤️ {liker_form.name} liked your Student Voice post."
                    )
                    db.session.add(notification)

            db.session.commit()
            return jsonify({
                'success': True,
                'liked': True,
                'likes_count': post.likes_count
            })

        except Exception:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return _inner()


@voice_api.route('/voice/me', methods=['GET'])
def get_my_posts():
    """Get current user's voice posts - NO RATE LIMIT (read-only)"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        user_form = Form.query.filter_by(user_id=user.id, active=True).first()
        if not user_form:
            return jsonify({'success': False, 'error': 'Profile not found'}), 400

        user_faculty_group = get_faculty_group(user_form.faculty)

        post = VoicePost.query.filter_by(
            user_id=user.id,
            faculty_group=user_faculty_group
        ).first()

        if not post:
            return jsonify({
                'success': True,
                'post': None,
                'faculty_group': user_faculty_group
            })

        return jsonify({
            'success': True,
            'post': {
                'id': post.id,
                'text': post.text,
                'likes_count': post.likes_count,
                'created_at': post.created_at.isoformat(),
                'faculty_group': post.faculty_group
            },
            'faculty_group': user_faculty_group
        })

    except Exception:
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@voice_api.route('/voice/me', methods=['DELETE'])
def delete_my_post():
    """Delete current user's voice post - MODERATE RATE LIMIT"""
    from main import limiter

    @limiter.limit("10 per hour")
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        try:
            data = request.get_json() or {}
            faculty = data.get('faculty')

            user_form = Form.query.filter_by(user_id=user.id, active=True).first()
            if not user_form:
                return jsonify({'success': False, 'error': 'Profile not found'}), 400

            user_faculty_group = get_faculty_group(user_form.faculty)

            if faculty and faculty != user_faculty_group:
                return jsonify({
                    'success': False,
                    'error': 'Cannot delete post from other faculty'
                }), 403

            post = VoicePost.query.filter_by(
                user_id=user.id,
                faculty_group=user_faculty_group
            ).first()

            if not post:
                return jsonify({'success': False, 'error': 'No post to delete'}), 404

            db.session.delete(post)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Post deleted'})

        except Exception:
            db.session.rollback()
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return _inner()


@voice_api.route('/notifications', methods=['GET'])
def get_notifications():
    """Get user's notifications - NO RATE LIMIT (read-only)"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 50)
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'

        query = Notification.query.filter_by(user_id=user.id)

        if unread_only:
            query = query.filter_by(is_read=False)

        query = query.order_by(Notification.created_at.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        notifications = []
        for notif in pagination.items:
            sender_info = None
            if notif.from_user_id:
                sender_form = Form.query.filter_by(
                    user_id=notif.from_user_id,
                    active=True
                ).first()
                if sender_form:
                    photo_thumb = None
                    photo_full = None

                    if sender_form.photo_thumb_path:
                        photo_thumb = f"/uploads/{sender_form.photo_thumb_path.split('/')[-1]}"
                    if sender_form.photo_path:
                        photo_full = f"/uploads/{sender_form.photo_path.split('/')[-1]}"

                    sender_info = {
                        'user_id': notif.from_user_id,
                        'name': sender_form.name,
                        'surname': sender_form.surname,
                        'photo_thumb_path': photo_thumb,
                        'photo_path': photo_full
                    }

            notifications.append({
                'id': notif.id,
                'type': notif.type,
                'message': notif.message,
                'is_read': notif.is_read,
                'created_at': notif.created_at.isoformat(),
                'post_id': notif.post_id,
                'sender': sender_info,
                'data': notif.data
            })

        unread_count = Notification.query.filter_by(
            user_id=user.id,
            is_read=False
        ).count()

        return jsonify({
            'success': True,
            'notifications': notifications,
            'unread_count': unread_count,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })

    except Exception:
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@voice_api.route('/notifications/<int:notification_id>/read', methods=['POST'])
def mark_notification_read(notification_id):
    """Delete notification when marked as read - NO RATE LIMIT (normal operation)"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        notification = Notification.query.filter_by(
            id=notification_id,
            user_id=user.id
        ).first()

        if not notification:
            return jsonify({'success': False, 'error': 'Notification not found'}), 404

        db.session.delete(notification)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Notification deleted'})

    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@voice_api.route('/notifications/read-all', methods=['POST'])
def mark_all_read():
    """Delete all unread notifications - NO RATE LIMIT (normal operation)"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        deleted_count = Notification.query.filter_by(
            user_id=user.id,
            is_read=False
        ).delete(synchronize_session=False)

        db.session.commit()

        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} notifications'
        })

    except Exception:
        db.session.rollback()
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@voice_api.route('/notifications/unread-count', methods=['GET'])
def get_unread_count():
    """Get count of unread notifications - NO RATE LIMIT (called frequently)"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        count = Notification.query.filter_by(
            user_id=user.id,
            is_read=False
        ).count()

        return jsonify({'success': True, 'unread_count': count})

    except Exception:
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
