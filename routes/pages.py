"""

Main pages routes: home, profile, search, etc.

"""
import logging
from flask import Blueprint, render_template, flash, redirect, url_for, session
from datetime import date
from sqlalchemy import text, func
from database.db import db

from database.db import User, Form

# Create Blueprint
pages_bp = Blueprint('pages', __name__)


def check_user_session():
    """Verify user session is valid"""
    if "user_id" not in session:
        return None

    user = User.query.get(session["user_id"])
    if not user:
        session.clear()
        return None

    return user


@pages_bp.route('/')

@pages_bp.route('/home')
def home():
    """Home page - shows form or student directory based on user state"""
    user = check_user_session()
    if not user:
        flash("⚠️ Please log in first or register.", "error")
        return redirect(url_for('auth.login'))

    existing_form = Form.query.filter_by(user_id=user.id, active=True).first()

    if not existing_form:
        return render_template("form.html")

    # ⭐ ИЗМЕНЕНО: Исключаем себя и делаем рандомный порядок

    # Seed для рандома (постоянный в течение дня)
    today = date.today()
    seed = (user.id + today.year * 10000 + today.month * 100 + today.day) % 1000000 / 1000000.0

    # Set seed
    db.session.execute(text(f"SELECT setseed({seed})"))

    # Load только первые 30 студентов (не себя)
    students = Form.query.filter(
        Form.active == True,
        Form.user_id != user.id  # Не показывать себя
    ).order_by(func.random()).limit(30).all()

    return render_template('home.html', students=students)


@pages_bp.route('/quotes')
def quotes():
    """Student Voice (Quotes) page"""
    user = check_user_session()
    if not user:
        flash("⚠️ Please log in first or register.", "error")
        return redirect(url_for('auth.login'))

    return render_template('quotes.html')


@pages_bp.route('/profile')
def profile():
    """Own profile page with edit capability"""
    user = check_user_session()
    if not user:
        flash("⚠️ Please log in first or register.", "error")
        return redirect(url_for('auth.login'))

    # Get user's own form
    student = Form.query.filter_by(user_id=user.id, active=True).first()

    if not student:
        flash("⚠️ Please complete your profile first.", "error")
        return redirect(url_for('pages.home'))

    return render_template('profile_view.html',student=student,is_own_profile=True)
@pages_bp.route('/notifications')
def notifications():
    """Notifications page"""
    user = check_user_session()
    if not user:
        flash("⚠️ Please log in first or register.", "error")
        return redirect(url_for('auth.login'))

    return render_template('notifications.html')  # ← было home.html


@pages_bp.route('/profile/<int:user_id>')
def student_profile(user_id):
    """Student profile page"""
    user = check_user_session()
    if not user:
        flash("⚠️ Please log in first or register.", "error")
        return redirect(url_for('auth.login'))

    # Get student data
    student = Form.query.filter_by(user_id=user_id, active=True).first()

    if not student:
        flash("❌ Student not found.", "error")
        return redirect(url_for('pages.home'))

    # Check if viewing own profile
    is_own_profile = (user.id == user_id)

    return render_template('profile_view.html', student=student, is_own_profile=is_own_profile)