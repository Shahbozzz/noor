"""
Input validation utilities
"""

from datetime import datetime
import re

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 70


def validate_birthday(birthday_str):
    """Validate birthday format and year range"""
    if not birthday_str or not birthday_str.strip():
        return True, None  # Optional field

    birthday_str = birthday_str.strip()

    # Check format
    if not re.match(r'^\d{4}/\d{2}/\d{2}$', birthday_str):
        return False, "Birthday must be in format YYYY/MM/DD (e.g., 2006/04/21)"

    try:
        birth_date = datetime.strptime(birthday_str, '%Y/%m/%d')

        # Check year range
        if birth_date.year < 2000 or birth_date.year > 2009:
            return False, "Birth year must be between 2000 and 2009"

        # Check not in future
        if birth_date > datetime.now():
            return False, "Birthday cannot be in the future"

        return True, None

    except ValueError:
        return False, "Invalid date. Please check the day and month values"

import re

def validate_email(email):
    """
    Validate email format for popular email providers
    
    Allowed domains:
    - @student.inha.uz (university email)
    - @gmail.com
    - @outlook.com, @hotmail.com
    - @yandex.ru, @yandex.com
    - @mail.ru
    
    Args:
        email (str): Email to validate
        
    Returns:
        bool: True if valid format and allowed domain
    """
    # List of allowed domains
    allowed_domains = [
        '@student.inha.uz',
        '@gmail.com',
        '@outlook.com',
        '@hotmail.com',
        '@yandex.ru',
        '@yandex.com',
        '@mail.ru',
	'@icloud.com'
    ]
    
    # Check if email ends with any allowed domain
    if not any(email.lower().endswith(domain) for domain in allowed_domains):
        return False
    
    # RFC 5322 compliant email regex
    # Allows letters, numbers, dots, hyphens, underscores, apostrophes, plus signs
    email_pattern = r'^[a-zA-Z0-9._%+\'-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    return bool(re.match(email_pattern, email.lower()))


def validate_password(password):
    """
    Validate password strength

    Args:
        password (str): Password to validate

    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    if not password or not isinstance(password, str):
        return False, "Password is required"

    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters long"

    if len(password) > MAX_PASSWORD_LENGTH:
        return False, f"Password must not exceed {MAX_PASSWORD_LENGTH} characters"


    return True, ""


def sanitize_email(email):
    """
    Normalize email address

    Args:
        email (str): Email to sanitize

    Returns:
        str: Normalized email (lowercase, stripped)
    """
    if not email:
        return ""
    return email.strip().lower()


def validate_form_field(value, field_name, max_length=None):
    """
    Validate form field

    Args:
        value (str): Field value
        field_name (str): Name of the field
        max_length (int, optional): Maximum length

    Returns:
        tuple: (bool, str) - (is_valid, error_message)
    """
    if not value or not value.strip():
        return False, f"{field_name} is required"

    if max_length and len(value.strip()) > max_length:
        return False, f"{field_name} must not exceed {max_length} characters"

    return True, ""
