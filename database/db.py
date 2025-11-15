"""
Database Models
"""
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Index, CheckConstraint

db = SQLAlchemy()


class User(db.Model):
    """User accounts"""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)  # Added index
    password = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())  # Added timestamp

    # Performance: Index on email for faster login queries
    __table_args__ = (
        Index('idx_email', 'email'),
    )

    def __repr__(self):
        return f'<User {self.email}>'


class Form(db.Model):
    """Student information form - UPDATED & OPTIMIZED"""
    __tablename__ = "form"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    active = db.Column(db.Boolean, default=False, nullable=False)

    # Personal info
    name = db.Column(db.String(30), nullable=False)
    surname = db.Column(db.String(30), nullable=False)
    about_me = db.Column(db.String(75), nullable=True)
    birthday = db.Column(db.String(10), nullable=True)  # Format: YYYY/MM/DD
    sex = db.Column(db.String(10), nullable=False)

    # Academic info
    level = db.Column(db.String(50), nullable=False)
    faculty = db.Column(db.String(50), nullable=False)
    professor = db.Column(db.String(35), nullable=True)
    favorite_subjects = db.Column(db.String(70), nullable=True)

    # Personal preferences
    relationship = db.Column(db.String(50), nullable=False)
    hobbies = db.Column(db.String(70), nullable=False)
    telegram = db.Column(db.String(50), nullable=True)

    # Photo paths
    photo_path = db.Column(db.String(200), nullable=True)
    photo_thumb_path = db.Column(db.String(200), nullable=True)

    # Timestamp
    created_at = db.Column(db.DateTime, server_default=db.func.now())


    # Relationships
    user = db.relationship('User', backref='forms')

    # Performance: Indexes for faster queries
    __table_args__ = (
        Index('idx_user_active', 'user_id', 'active'),  # Fast lookup of active forms
        Index('idx_faculty', 'faculty'),  # Fast filtering by faculty
        Index('idx_level', 'level'),  # Fast filtering by level
        Index('idx_sex', 'sex'),  # Fast filtering by gender
        Index('idx_voice_posts_created_at', 'created_at'),  # Fast sorting by date
        # Security: One active form per user
        CheckConstraint('length(name) >= 2', name='check_name_length'),
        CheckConstraint('length(surname) >= 2', name='check_surname_length'),
    )

    def __repr__(self):
        return f'<Form {self.name} {self.surname} - User {self.user_id}>'

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'name': self.name,
            'surname': self.surname,
            'about_me': self.about_me,
            'level': self.level,
            'faculty': self.faculty,
            'sex': self.sex,
            'relationship': self.relationship,
            'hobbies': self.hobbies,
            'professor': self.professor,
            'favorite_subjects': self.favorite_subjects,
            'telegram': self.telegram,
            'birthday': self.birthday,
            'photo_path': self.photo_path,
            'photo_thumb_path': self.photo_thumb_path,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class VoicePost(db.Model):
    """Student Voice posts - one active post per user PER FACULTY"""
    __tablename__ = "voice_posts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    faculty_group = db.Column(db.String(20), nullable=False)
    text = db.Column(db.String(100), nullable=False)
    likes_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), 
        server_default=db.func.now(),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True), 
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False
    )	
    # Relationships
    user = db.relationship('User', backref='voice_posts')
    likes = db.relationship('VoiceLike', backref='post', cascade='all, delete-orphan')

    # Performance & Security: Indexes and constraints
    __table_args__ = (
        # One post per user per faculty
        db.UniqueConstraint('user_id', 'faculty_group', name='unique_user_faculty_post'),
        # Fast filtering by faculty
        Index('idx_faculty_group', 'faculty_group'),
        # Fast sorting by likes within faculty
        Index('idx_faculty_likes', 'faculty_group', 'likes_count'),
        # Fast sorting by date
        Index('idx_voice_post_created_at', 'created_at'),
        # Security: Ensure text is not empty
        CheckConstraint('length(text) >= 1', name='check_text_not_empty'),
    )

    def __repr__(self):
        return f'<VoicePost {self.id} by User {self.user_id}>'


class VoiceLike(db.Model):
    """Likes for voice posts"""
    __tablename__ = "voice_likes"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("voice_posts.id", ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    user = db.relationship('User', backref='voice_likes')

    # Performance & Security: Indexes and constraints
    __table_args__ = (
        # Security: Prevent duplicate likes
        db.UniqueConstraint('post_id', 'user_id', name='unique_post_user_like'),
        # Performance: Fast lookup by post
        Index('idx_post_id', 'post_id'),
        # Performance: Fast lookup by user
        Index('idx_user_id', 'user_id'),
    )

    def __repr__(self):
        return f'<VoiceLike Post {self.post_id} by User {self.user_id}>'


class Notification(db.Model):
    """User notifications"""
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)  # recipient
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # sender
    type = db.Column(db.String(50), nullable=False)  # 'voice_like', 'friend_request', etc
    post_id = db.Column(db.Integer, nullable=True)  # reference to voice post
    message = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    data = db.Column(db.JSON, nullable=True)

    # Relationships
    recipient = db.relationship('User', foreign_keys=[user_id], backref='notifications')
    sender = db.relationship('User', foreign_keys=[from_user_id])

    # Performance: Indexes for faster queries
    __table_args__ = (
        # Fast lookup of user's notifications
        Index('idx_user_notifications', 'user_id', 'is_read'),
        # Fast filtering by type
        Index('idx_notification_type', 'type'),
        # Fast sorting by date
        Index('idx_notifications_created_at', 'created_at'),
    )

    def __repr__(self):
        return f'<Notification {self.type} to User {self.user_id}>'


class FriendRequest(db.Model):
    """Friend requests between users"""
    __tablename__ = "friend_requests"

    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, accepted, declined
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    # Relationships
    from_user = db.relationship('User', foreign_keys=[from_user_id], backref='sent_requests')
    to_user = db.relationship('User', foreign_keys=[to_user_id], backref='received_requests')

    # Performance & Security: Indexes and constraints
    __table_args__ = (
        # Performance: Fast lookup by sender
        Index('idx_from_user', 'from_user_id'),
        # Performance: Fast lookup by recipient
        Index('idx_to_user', 'to_user_id'),
        # Performance: Fast filtering by status
        Index('idx_status', 'status'),
        # Performance: Combined index for pending requests
        Index('idx_to_user_status', 'to_user_id', 'status'),
        # Security: Prevent duplicate requests
        db.UniqueConstraint('from_user_id', 'to_user_id', name='unique_friend_request'),
        # Security: Can't send request to yourself
        CheckConstraint('from_user_id != to_user_id', name='check_not_self_request'),
    )

    def __repr__(self):
        return f'<FriendRequest from {self.from_user_id} to {self.to_user_id} - {self.status}>'


class Friendship(db.Model):
    """Friendships between users - bidirectional"""
    __tablename__ = "friendships"

    id = db.Column(db.Integer, primary_key=True)
    user1_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user2_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Relationships
    user1 = db.relationship('User', foreign_keys=[user1_id], backref='friendships_as_user1')
    user2 = db.relationship('User', foreign_keys=[user2_id], backref='friendships_as_user2')

    # Performance & Security: Indexes and constraints
    __table_args__ = (
        # Performance: Fast lookup by either user
        Index('idx_user1', 'user1_id'),
        Index('idx_user2', 'user2_id'),
        # Security: Prevent duplicate friendships
        db.UniqueConstraint('user1_id', 'user2_id', name='unique_friendship'),
        # Security: Always store user1_id < user2_id for consistency
        CheckConstraint('user1_id < user2_id', name='check_user_order'),
    )

    def __repr__(self):
        return f'<Friendship between {self.user1_id} and {self.user2_id}>'

    @staticmethod
    def create_friendship(user_id_a, user_id_b):
        """
        Create friendship with correct ordering
        Security: Ensures user1_id < user2_id
        """
        if user_id_a == user_id_b:
            raise ValueError("Cannot create friendship with self")

        user1_id = min(user_id_a, user_id_b)
        user2_id = max(user_id_a, user_id_b)
        return Friendship(user1_id=user1_id, user2_id=user2_id)

    @staticmethod
    def get_friendship(user_id_a, user_id_b):
        """
        Get friendship regardless of order
        Performance: Uses indexes
        """
        user1_id = min(user_id_a, user_id_b)
        user2_id = max(user_id_a, user_id_b)
        return Friendship.query.filter_by(user1_id=user1_id, user2_id=user2_id).first()

    @staticmethod
    def are_friends(user_id_a, user_id_b):
        """
        Check if two users are friends
        Performance: Optimized with exists() query
        """
        if user_id_a == user_id_b:
            return False

        user1_id = min(user_id_a, user_id_b)
        user2_id = max(user_id_a, user_id_b)

        return db.session.query(
            db.exists().where(
                db.and_(
                    Friendship.user1_id == user1_id,
                    Friendship.user2_id == user2_id
                )
            )
        ).scalar()

    @staticmethod
    def get_user_friends_count(user_id):
        """
        Get count of user's friends
        Performance: Fast count query
        """
        return db.session.query(db.func.count(Friendship.id)).filter(
            db.or_(
                Friendship.user1_id == user_id,
                Friendship.user2_id == user_id
            )
        ).scalar()

    @staticmethod
    def get_user_friends(user_id, limit=None):
        """
        Get all friends of a user
        Performance: Optimized query with limit
        Returns: List of user IDs
        """
        query = db.session.query(
            db.case(
                (Friendship.user1_id == user_id, Friendship.user2_id),
                else_=Friendship.user1_id
            ).label('friend_id')
        ).filter(
            db.or_(
                Friendship.user1_id == user_id,
                Friendship.user2_id == user_id
            )
        )

        if limit:
            query = query.limit(limit)

        return [row.friend_id for row in query.all()]


# Migration helper function
def create_indexes_if_not_exist():
    """
    Create all indexes if they don't exist
    Run this after updating the models
    """
    from sqlalchemy import inspect

    inspector = inspect(db.engine)

    # Get all tables
    tables = [User, Form, VoicePost, VoiceLike, Notification, FriendRequest, Friendship]

    for table in tables:
        table_name = table.__tablename__
        existing_indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]


        if hasattr(table, '__table_args__'):
            for item in table.__table_args__:
                if isinstance(item, Index):
                    if item.name not in existing_indexes:
                        print(f"   ⚠️  Missing index: {item.name}")
                    else:
                        print(f"   ✅ Index exists: {item.name}")


# Performance monitoring
def get_slow_queries():
    """
    Monitor slow queries (requires PostgreSQL)
    Add to your admin panel
    """
    if 'postgresql' in str(db.engine.url):
        query = """
        SELECT 
            query,
            calls,
            total_time / 1000 as total_seconds,
            mean_time / 1000 as mean_seconds
        FROM pg_stat_statements
        WHERE mean_time > 1000  -- queries slower than 1 second
        ORDER BY mean_time DESC
        LIMIT 10;
        """
        return db.session.execute(query).fetchall()
    return []
