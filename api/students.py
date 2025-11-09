"""
API endpoints for students - pagination and filtering (OPTIMIZED - NO RATE LIMIT)
"""
from flask import Blueprint, jsonify, request
from database.db import Form
from sqlalchemy import or_, func
from api.helpers import check_api_auth
from datetime import date

# Create API Blueprint
students_api = Blueprint('students_api', __name__, url_prefix='/api')


@students_api.route('/students', methods=['GET'])
def get_students():
    """
    Get paginated and filtered students
    Requires authentication

    ⭐ NO RATE LIMIT - This endpoint loads many images, rate limiting causes issues

    Query params:
    - page: int (default 1)
    - per_page: int (default 30)
    - faculty: string (optional)
    - level: string (optional)
    """
    user = check_api_auth()
    if not user:
        return jsonify({
            'success': False,
            'error': 'Unauthorized. Please log in.'
        }), 401

    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 30, type=int)
        faculty = request.args.get('faculty', '')
        level = request.args.get('level', '')

        # ⭐ Limit max items to prevent overload
        per_page = min(per_page, 100)

        # ⭐ Exclude current user
        query = Form.query.filter(
            Form.active == True,
            Form.user_id != user.id
        )

        if faculty and faculty != 'all':
            query = query.filter(Form.faculty == faculty)

        if level and level != 'all':
            query = query.filter(Form.level == level)

        # ⭐ Random order with daily seed (stable randomness throughout the day)
        today = date.today()
        seed = (user.id + today.year * 10000 + today.month * 100 + today.day) % 1000000 / 1000000.0

        # Set seed for PostgreSQL
        from sqlalchemy import text
        from database.db import db
        db.session.execute(text(f"SELECT setseed({seed})"))

        # Random order
        query = query.order_by(func.random())

        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        students = []
        for student in pagination.items:
            students.append({
                'user_id': student.user_id,
                'name': student.name,
                'surname': student.surname,
                'faculty': student.faculty,
                'level': student.level,
                'hobbies': student.hobbies,
                'favorite_subjects': student.favorite_subjects,
                'relationship': student.relationship,
                'sex': student.sex,  # ⭐ ДОБАВЛЕНО для gender-based colors
                'photo_path': student.photo_path,
                'photo_thumb_path': student.photo_thumb_path
            })

        return jsonify({
            'success': True,
            'students': students,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })

    except Exception as e:
        print(f"Error in get_students: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@students_api.route('/search', methods=['GET'])
def search_students():
    """
    Search students by name or surname

    ⭐ NO RATE LIMIT - Search is a core feature, should not be limited
    """
    user = check_api_auth()
    if not user:
        return jsonify({
            'success': False,
            'error': 'Unauthorized. Please log in.'
        }), 401

    try:
        query = request.args.get('q', '').strip()

        if len(query) < 2:
            return jsonify({
                'success': True,
                'students': [],
                'total': 0
            })

        search_filter = or_(
            Form.name.ilike(f'%{query}%'),
            Form.surname.ilike(f'%{query}%')
        )

        # ⭐ Exclude current user from search
        results = Form.query.filter(
            Form.active == True,
            Form.user_id != user.id,
            search_filter
        ).limit(30).all()

        students = []
        for student in results:
            students.append({
                'user_id': student.user_id,
                'name': student.name,
                'surname': student.surname,
                'faculty': student.faculty,
                'level': student.level,
                'hobbies': student.hobbies,
                'favorite_subjects': student.favorite_subjects,
                'relationship': student.relationship,
                'sex': student.sex,  # ⭐ ДОБАВЛЕНО для gender-based colors
                'photo_path': student.photo_path,
                'photo_thumb_path': student.photo_thumb_path
            })

        return jsonify({
            'success': True,
            'students': students,
            'total': len(students)
        })

    except Exception as e:
        print(f"Search error: {e}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500