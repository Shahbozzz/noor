"""
API endpoints for Friend System 
"""
from flask import Blueprint, jsonify, request, session
from sqlalchemy import or_, and_
from database.db import db, User, Form, FriendRequest, Friendship, Notification
from api.helpers import check_api_auth

friends_api = Blueprint('friends_api', __name__, url_prefix='/api/friends')


# ----------------------------
# Send Friend Request 
# ----------------------------
@friends_api.route('/request', methods=['POST'])
def send_friend_request():
    """Send friend request - with proper duplicate checking"""
    from main import limiter
    @limiter.limit("20 per minute")  
    def _inner():
        user = check_api_auth()
        if not user:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 401

        data = request.get_json()
        to_user_id = data.get('to_user_id')

        if not to_user_id:
            return jsonify({'success': False, 'error': 'Missing user ID'}), 400

        if to_user_id == user.id:
            return jsonify({'success': False, 'error': 'Cannot add yourself'}), 400

        try:
            
            if Friendship.are_friends(user.id, to_user_id):
                return jsonify({'success': False, 'error': 'Already friends'}), 400

            
            existing_pending = FriendRequest.query.filter(
                or_(
                    and_(FriendRequest.from_user_id == user.id, FriendRequest.to_user_id == to_user_id),
                    and_(FriendRequest.from_user_id == to_user_id, FriendRequest.to_user_id == user.id)
                ),
                FriendRequest.status == 'pending'
            ).first()

            if existing_pending:
            
                if existing_pending.from_user_id == to_user_id:
                    # They sent you a request - tell user to accept it
                    return jsonify({
                        'success': False,
                        'has_incoming': True,
                        'request_id': existing_pending.id,
                        'status': 'pending_received',
                        'message': 'This user already sent you a friend request!'
                    }), 400
                else:
                    # You already sent a request
                    return jsonify({
                        'success': False,
                        'status': 'pending_sent',
                        'error': 'Friend request already sent'
                    }), 400

            # This allows users to send new requests after being declined
            old_declined = FriendRequest.query.filter(
                and_(FriendRequest.from_user_id == user.id, FriendRequest.to_user_id == to_user_id),
                FriendRequest.status.in_(['declined', 'rejected'])
            ).all()

            for old_request in old_declined:
                db.session.delete(old_request)
                print(f"Deleted old {old_request.status} request from {user.id} to {to_user_id}")

            if old_declined:
                db.session.flush()  # Commit the deletions before creating new request

            # All checks passed - create new request
            friend_request = FriendRequest(
                from_user_id=user.id,
                to_user_id=to_user_id,
                status='pending'
            )
            db.session.add(friend_request)
            db.session.flush()

            # Create notification 
            sender_form = Form.query.filter_by(user_id=user.id, active=True).first()
            if sender_form:
                try:
                    notification = Notification(
                        user_id=to_user_id,
                        from_user_id=user.id,
                        type='friend_request',
                        message=f"👋 {sender_form.name} {sender_form.surname} sent you a friend request!",
                        data={'request_id': friend_request.id}
                    )
                    db.session.add(notification)
                except Exception as e:
                    print(f"Warning: notification error: {e}")

            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Friend request sent',
                'status': 'pending_sent'
            })

        except Exception as e:
            db.session.rollback()
            print(f"Error sending friend request: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': 'Internal server error'}), 500

    return _inner()


# ----------------------------
# Accept Friend Request
# ----------------------------
@friends_api.route('/accept/<int:request_id>', methods=['POST'])
def accept_friend_request(request_id):
    """Accept friend request - fast"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401
    
    try:
        
        friend_request = FriendRequest.query.filter_by(
            id=request_id,
            to_user_id=user.id
        ).filter(
            FriendRequest.status.in_(['pending', 'accepted'])
        ).first()
        
        if not friend_request:
            return jsonify({'success': False, 'error': 'Request not found'}), 404
        
        from_user_id = friend_request.from_user_id
        
        if Friendship.are_friends(user.id, from_user_id):
            # Дружба уже существует - просто обновить статус запроса
            if friend_request.status == 'pending':
                friend_request.status = 'accepted'
                db.session.commit()
            return jsonify({'success': True, 'message': 'Already friends'})
        
        existing_friendship = Friendship.query.filter(
            db.or_(
                db.and_(
                    Friendship.user1_id == min(user.id, from_user_id),
                    Friendship.user2_id == max(user.id, from_user_id)
                ),
                db.and_(
                    Friendship.user1_id == max(user.id, from_user_id),
                    Friendship.user2_id == min(user.id, from_user_id)
                )
            )
        ).first()
        
        if existing_friendship:
            if friend_request.status == 'pending':
                friend_request.status = 'accepted'
                db.session.commit()
            return jsonify({'success': True, 'message': 'Already friends'})
        
        friendship = Friendship.create_friendship(user.id, from_user_id)
        db.session.add(friendship)
        
        if friend_request.status == 'pending':
            friend_request.status = 'accepted'
        
        db.session.commit()
        
        try:
            recipient_form = Form.query.filter_by(user_id=user.id, active=True).first()
            if recipient_form:
                notification = Notification(
                    user_id=from_user_id,
                    from_user_id=user.id,
                    type='friend_accepted',
                    message=f"✅ {recipient_form.name} {recipient_form.surname} accepted your friend request!",
                    data=None
                )
                db.session.add(notification)
                db.session.commit()
        except Exception as notif_error:
            print(f"Warning: Could not create notification: {notif_error}")
        
        return jsonify({'success': True, 'message': 'Friend request accepted'})
        
    except Exception as e:
        db.session.rollback()
        print(f"Error accepting friend request: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

# ----------------------------
# Decline Friend Request
# ----------------------------
@friends_api.route('/decline/<int:request_id>', methods=['POST'])
def decline_friend_request(request_id):
    """Decline friend request"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        friend_request = FriendRequest.query.filter_by(
            id=request_id,
            to_user_id=user.id,
            status='pending'
        ).first()

        if not friend_request:
            return jsonify({'success': False, 'error': 'Request not found'}), 404

        from_user_id = friend_request.from_user_id

        friend_request.status = 'declined'

        recipient_form = Form.query.filter_by(user_id=user.id, active=True).first()
        if recipient_form:
            notification = Notification(
                user_id=from_user_id,
                from_user_id=user.id,
                type='friend_declined',
                message=f"{recipient_form.name} {recipient_form.surname} declined your friend request."
            )
            db.session.add(notification)

        db.session.commit()

        return jsonify({'success': True, 'message': 'Friend request declined'})

    except Exception as e:
        db.session.rollback()
        print(f"Error declining friend request: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ----------------------------
# Remove Friend
# ----------------------------
@friends_api.route('/<int:friend_user_id>', methods=['DELETE'])
def remove_friend(friend_user_id):
    """Remove friend - bidirectional"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        friendship = Friendship.get_friendship(user.id, friend_user_id)

        if not friendship:
            return jsonify({'success': False, 'error': 'Not friends'}), 404

        db.session.delete(friendship)

        FriendRequest.query.filter(
            or_(
                and_(FriendRequest.from_user_id == user.id, FriendRequest.to_user_id == friend_user_id),
                and_(FriendRequest.from_user_id == friend_user_id, FriendRequest.to_user_id == user.id)
            ),
            FriendRequest.status == 'accepted'
        ).delete(synchronize_session=False)

        db.session.commit()

        return jsonify({'success': True, 'message': 'Friend removed'})

    except Exception as e:
        db.session.rollback()
        print(f"Error removing friend: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ----------------------------
# Get Friends List
# ----------------------------
@friends_api.route('', methods=['GET'])
def get_friends():
    """Get user's friends list - optimized with pagination"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 50)

        target_user_id = request.args.get('user_id', type=int)
        if not target_user_id:
            target_user_id = user.id

        friendships = Friendship.query.filter(
            or_(
                Friendship.user1_id == target_user_id,
                Friendship.user2_id == target_user_id
            )
        ).paginate(page=page, per_page=per_page, error_out=False)

        friends = []
        for friendship in friendships.items:
            friend_id = friendship.user2_id if friendship.user1_id == target_user_id else friendship.user1_id

            friend_form = Form.query.filter_by(user_id=friend_id, active=True).first()
            if friend_form:
                friends.append({
                    'user_id': friend_id,
                    'name': friend_form.name,
                    'surname': friend_form.surname,
                    'faculty': friend_form.faculty,
                    'level': friend_form.level,
                    'photo_thumb_path': f"/uploads/{friend_form.photo_thumb_path.split('/')[-1]}" if friend_form.photo_thumb_path else None,
                    'photo_path': f"/uploads/{friend_form.photo_path.split('/')[-1]}" if friend_form.photo_path else None,
                    'friendship_since': friendship.created_at.isoformat()
                })

        return jsonify({
            'success': True,
            'friends': friends,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': friendships.total,
                'pages': friendships.pages,
                'has_next': friendships.has_next,
                'has_prev': friendships.has_prev
            }
        })

    except Exception as e:
        print(f"Error getting friends: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ----------------------------
# Check Friend Status (Single)
# ----------------------------
@friends_api.route('/status/<int:other_user_id>', methods=['GET'])
def get_friend_status(other_user_id):
    """Get friendship status with another user - fast"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        if Friendship.are_friends(user.id, other_user_id):
            return jsonify({'success': True, 'status': 'friends'})

        sent_request = FriendRequest.query.filter_by(
            from_user_id=user.id,
            to_user_id=other_user_id,
            status='pending'
        ).first()

        if sent_request:
            return jsonify({'success': True, 'status': 'pending_sent', 'request_id': sent_request.id})

        received_request = FriendRequest.query.filter_by(
            from_user_id=other_user_id,
            to_user_id=user.id,
            status='pending'
        ).first()

        if received_request:
            return jsonify({'success': True, 'status': 'pending_received', 'request_id': received_request.id})

        return jsonify({'success': True, 'status': None})

    except Exception as e:
        print(f"Error checking friend status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


# ----------------------------
# Batch Check Status (FAST!)
# ----------------------------
@friends_api.route('/status/batch', methods=['POST'])
def batch_friend_status():
    """Check status for multiple users at once - OPTIMIZED"""
    user = check_api_auth()
    if not user:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 401

    try:
        data = request.get_json()
        user_ids = data.get('user_ids', [])

        if not user_ids or len(user_ids) > 100:
            return jsonify({'success': False, 'error': 'Invalid user_ids'}), 400

        statuses = {}

        friendships = Friendship.query.filter(
            or_(
                and_(Friendship.user1_id == user.id, Friendship.user2_id.in_(user_ids)),
                and_(Friendship.user2_id == user.id, Friendship.user1_id.in_(user_ids))
            )
        ).all()

        friend_ids = set()
        for f in friendships:
            friend_id = f.user2_id if f.user1_id == user.id else f.user1_id
            friend_ids.add(friend_id)
            statuses[friend_id] = 'friends'

        sent_requests = FriendRequest.query.filter(
            FriendRequest.from_user_id == user.id,
            FriendRequest.to_user_id.in_(user_ids),
            FriendRequest.status == 'pending'
        ).all()

        for req in sent_requests:
            if req.to_user_id not in friend_ids:
                statuses[req.to_user_id] = {'status': 'pending_sent', 'request_id': req.id}

        received_requests = FriendRequest.query.filter(
            FriendRequest.from_user_id.in_(user_ids),
            FriendRequest.to_user_id == user.id,
            FriendRequest.status == 'pending'
        ).all()

        for req in received_requests:
            if req.from_user_id not in friend_ids:
                statuses[req.from_user_id] = {'status': 'pending_received', 'request_id': req.id}

        for uid in user_ids:
            if uid not in statuses:
                statuses[uid] = None

        return jsonify({'success': True, 'statuses': statuses})

    except Exception as e:
        print(f"Error batch checking statuses: {e}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500
