"""
Initialize database - run once!
"""
from main import app, db

with app.app_context():
    print("Creating tables...")
    db.create_all()
    print("✅ All tables created!")

