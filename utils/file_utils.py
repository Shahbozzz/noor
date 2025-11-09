"""
File handling utilities with image optimization
"""
import os
import secrets
from werkzeug.utils import secure_filename
from PIL import Image, ImageOps, ImageDraw

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 2 MB


def allowed_file(filename):
    """
    Check if file extension is allowed

    Args:
        filename (str): Original filename

    Returns:
        bool: True if allowed, False otherwise
    """
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def sanitize_filename(user_id, original_filename):
    """
    Create a safe, unique filename to prevent path traversal attacks

    Args:
        user_id (int): User ID
        original_filename (str): Original filename

    Returns:
        str: Safe filename
    """
    if not original_filename or "." not in original_filename:
        return f"user_{user_id}_{secrets.token_hex(8)}.jpg"

    ext = original_filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        ext = "jpg"

    return f"user_{user_id}_{secrets.token_hex(8)}.{ext}"


def validate_file_upload(file):
    """
    Validate uploaded file

    Args:
        file: FileStorage object from Flask

    Returns:
        tuple: (is_valid, error_message)
    """
    if not file or file.filename == "":
        return True, ""  # No file is OK (optional upload)

    # Check extension
    if not allowed_file(file.filename):
        return False, "Only JPG, JPEG, PNG, WEBP files are allowed"

    # Check file size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)  # Reset position

    if size > MAX_FILE_SIZE:
        return False, f"File too large (max {MAX_FILE_SIZE // (1024*1024)}MB)"

    if size == 0:
        return False, "File is empty"

    return True, ""


def save_uploaded_file(file, upload_folder, user_id):
    """
    Save uploaded file securely (OLD VERSION - use optimize_and_save_profile_photo instead)

    Args:
        file: FileStorage object from Flask
        upload_folder (str): Path to upload folder
        user_id (int): User ID

    Returns:
        str or None: Full path to saved file, or None if failed
    """
    if not file or file.filename == "":
        return None

    # Validate file
    is_valid, error = validate_file_upload(file)
    if not is_valid:
        raise ValueError(error)

    # Create safe filename
    safe_filename = sanitize_filename(user_id, file.filename)
    save_path = os.path.join(upload_folder, safe_filename)

    # Save file
    file.save(save_path)

    return save_path


def delete_file(file_path):
    """
    Safely delete a file

    Args:
        file_path (str): Path to file

    Returns:
        bool: True if deleted, False otherwise
    """
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            return True
    except Exception:
        pass
    return False


# ============== IMAGE OPTIMIZATION FUNCTIONS ==============

def create_circular_thumbnail(image, size=(200, 200)):
    """
    Create a circular thumbnail from image

    Args:
        image: PIL Image object
        size: Tuple of (width, height)

    Returns:
        PIL Image: Circular thumbnail
    """
    # Resize to square
    image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)

    # Create circular mask
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)

    # Apply mask
    output = ImageOps.fit(image, size, centering=(0.5, 0.5))
    output.putalpha(mask)

    return output


def optimize_and_save_profile_photo(uploaded_file, upload_folder, user_id):
    """
    Process uploaded photo: create optimized versions

    Creates:
    - Original optimized version (max 1000x1000, WebP)
    - Thumbnail version (200x200, WebP, circular)

    Args:
        uploaded_file: FileStorage object from Flask
        upload_folder: Path to upload directory
        user_id: User ID for filename

    Returns:
        tuple: (original_path, thumbnail_path)
    """
    # Validate file first
    is_valid, error = validate_file_upload(uploaded_file)
    if not is_valid:
        raise ValueError(error)

    # Generate unique filename
    unique_id = secrets.token_hex(8)
    base_filename = f"user_{user_id}_{unique_id}"

    # Open and process image
    image = Image.open(uploaded_file)

    # Convert RGBA to RGB if necessary
    if image.mode in ('RGBA', 'LA', 'P'):
        background = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'P':
            image = image.convert('RGBA')
        background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
        image = background

    # Fix orientation (from EXIF data)
    image = ImageOps.exif_transpose(image)

    # === ORIGINAL VERSION (optimized) ===
    # Resize if too large (max 1000x1000)
    max_size = (1000, 1000)
    original_image = image.copy()
    if original_image.size[0] > max_size[0] or original_image.size[1] > max_size[1]:
        original_image.thumbnail(max_size, Image.Resampling.LANCZOS)

    # Save as WebP (much smaller than JPG!)
    original_filename = f"{base_filename}.webp"
    original_path = os.path.join(upload_folder, original_filename)
    original_image.save(original_path, 'WEBP', quality=85, method=6)

    # === THUMBNAIL VERSION (200x200, circular) ===
    thumbnail = create_circular_thumbnail(image, size=(200, 200))
    thumbnail_filename = f"{base_filename}_thumb.webp"
    thumbnail_path = os.path.join(upload_folder, thumbnail_filename)
    thumbnail.save(thumbnail_path, 'WEBP', quality=85, method=6)

    return original_path, thumbnail_path


def get_default_avatar(sex, upload_folder):
    """
    Get default avatar path based on gender

    Args:
        sex: 'male' or 'female'
        upload_folder: Upload folder path

    Returns:
        tuple: (original_path, thumbnail_path)
    """
    if sex.lower() == "male":
        default_original = os.path.join(upload_folder, "default_male.webp")
        default_thumb = os.path.join(upload_folder, "default_male_thumb.webp")
    elif sex.lower() == "female":
        default_original = os.path.join(upload_folder, "default_female.webp")
        default_thumb = os.path.join(upload_folder, "default_female_thumb.webp")
    else:
        default_original = os.path.join(upload_folder, "default.webp")
        default_thumb = os.path.join(upload_folder, "default_thumb.webp")

    return default_original, default_thumb


def create_default_avatars(upload_folder):
    """
    Create default avatars for male/female if they don't exist
    Call this once on app startup

    Args:
        upload_folder: Path to uploads folder
    """
    # Check if default avatars exist
    male_original = os.path.join(upload_folder, "default_male.webp")
    male_thumb = os.path.join(upload_folder, "default_male_thumb.webp")
    female_original = os.path.join(upload_folder, "default_female.webp")
    female_thumb = os.path.join(upload_folder, "default_female_thumb.webp")

    # If you have default PNG files, convert them
    male_png = os.path.join(upload_folder, "male_iut.png")
    female_png = os.path.join(upload_folder, "female_iut.png")

    if os.path.exists(male_png) and not os.path.exists(male_original):
        try:
            # Convert male default
            img = Image.open(male_png)
            img = img.convert('RGB')
            img.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
            img.save(male_original, 'WEBP', quality=85)

            # Create thumbnail
            thumb = create_circular_thumbnail(img, (200, 200))
            thumb.save(male_thumb, 'WEBP', quality=85)

        except Exception as e:
            print(f"❌ Error creating male avatar: {e}")

    if os.path.exists(female_png) and not os.path.exists(female_original):
        try:
            # Convert female default
            img = Image.open(female_png)
            img = img.convert('RGB')
            img.thumbnail((1000, 1000), Image.Resampling.LANCZOS)
            img.save(female_original, 'WEBP', quality=85)

            # Create thumbnail
            thumb = create_circular_thumbnail(img, (200, 200))
            thumb.save(female_thumb, 'WEBP', quality=85)

        except Exception as e:
            print(f"❌ Error creating female avatar: {e}")


def delete_user_photos(photo_path, thumbnail_path):
    """
    Delete user's photos (original and thumbnail)

    Args:
        photo_path: Path to original photo
        thumbnail_path: Path to thumbnail

    Returns:
        bool: True if deleted, False otherwise
    """
    success = True

    try:
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
    except Exception:
        success = False

    try:
        if thumbnail_path and os.path.exists(thumbnail_path):
            os.remove(thumbnail_path)
    except Exception:
        success = False

    return success