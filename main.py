"""
Main Flask application - Entry point
All routes are in separate blueprint modules
"""
import os
import logging
import json
from flask import Flask, render_template, request, session, send_from_directory
from flask_wtf.csrf import CSRFProtect
from flask_session import Session

from api.voice import voice_api
from config import get_config
from database.db import db, User, Form
from utils.file_utils import create_default_avatars
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Import blueprints
from routes import auth_bp, password_reset_bp, forms_bp, pages_bp
from api.students import students_api
from api.friends import friends_api
from api.profile_edit import profile_edit_api

# ✅ Import Redis clients (session = bytes, cache = strings)
from utils.redis_client import redis_client_session, redis_client

# --- Initialize Flask app ---
app = Flask(__name__)
app.config.from_object(get_config())

# ✅ Flask-Session uses redis_client_session (decode_responses=False for pickle)
app.config['SESSION_REDIS'] = redis_client_session

# ✅ Initialize Flask-Session
Session(app)

# --- CSRF Protection ---
csrf = CSRFProtect(app)

# --- Logging ---
logging.basicConfig(
    filename=app.config['LOG_FILE'],
    level=app.config['LOG_LEVEL'],
    format="%(asctime)s - %(levelname)s - %(message)s"
)

@app.before_request
def log_request():
    """Log incoming requests"""
    logging.info(f"{request.remote_addr} → {request.method} {request.path}")

# --- Initialize Database ---
db.init_app(app)

# ... остальное без изменений
# Initialize limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://"
)

@limiter.request_filter
def exempt_uploads():
    """Don't rate limit image/static file requests"""
    return request.path.startswith('/uploads') or request.path.startswith('/static')

with app.app_context():
    db.create_all()
    create_default_avatars(app.config["UPLOAD_FOLDER"])

# --- Create upload folder ---
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# ✅ ПЕРЕПИСАНО: Context Processor с Redis кешированием
@app.context_processor
def inject_user():
    """
    Automatically inject current_user into all templates
    Now uses Redis for caching instead of session cookies!
    """
    if "user_id" not in session:
        return dict(current_user=None)

    user_id = session.get("user_id")

    # ✅ Попробовать загрузить из Redis кеша
    cache_key = f"user_cache:{user_id}"
    cached_data = redis_client.get(cache_key)

    if cached_data:
        # Кеш найден - вернуть без запроса к БД!
        user_data = json.loads(cached_data)
        return dict(current_user=type('obj', (object,), user_data))

    # Кеша нет - загрузить из БД и закешировать
    user = User.query.get(user_id)
    if user:
        form = Form.query.filter_by(user_id=user.id, active=True).first()
        if form:
            # Сохранить в Redis кеш на 5 минут
            cache_data = {
                'sex': form.sex,
                'name': form.name,
                'surname': form.surname,
                'user_id': form.user_id
            }
            redis_client.setex(
                cache_key,
                300,  # 5 минут TTL
                json.dumps(cache_data)
            )
            return dict(current_user=type('obj', (object,), cache_data))

    return dict(current_user=None)


# ✅ ОБНОВЛЕНО: Refresh cache теперь использует Redis
def refresh_user_cache(user_id=None):
    """
    Helper function to refresh user cache after profile updates
    Call this in profile_edit_api after successful updates
    """
    if user_id is None:
        user_id = session.get("user_id")

    if not user_id:
        return

    # Удалить старый кеш
    cache_key = f"user_cache:{user_id}"
    redis_client.delete(cache_key)

    # Создать новый кеш
    user = User.query.get(user_id)
    if user:
        form = Form.query.filter_by(user_id=user.id, active=True).first()
        if form:
            cache_data = {
                'sex': form.sex,
                'name': form.name,
                'surname': form.surname,
                'user_id': form.user_id
            }
            redis_client.setex(
                cache_key,
                300,  # 5 минут
                json.dumps(cache_data)
            )

# --- Register Blueprints ---
app.register_blueprint(auth_bp)
app.register_blueprint(password_reset_bp)
app.register_blueprint(forms_bp)
app.register_blueprint(pages_bp)
app.register_blueprint(students_api)
app.register_blueprint(voice_api)
app.register_blueprint(friends_api)
app.register_blueprint(profile_edit_api)

# --- Serve uploaded files ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- Error Handlers ---
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    logging.error(f"Internal error: {e}")
    return render_template('500.html'), 500

# --- Run Application ---
if __name__ == '__main__':
    app.run(debug=True, port=5000)
