"""
Email utility functions
"""
import os
import ssl
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def get_base_url():
    """
    Get base URL based on environment

    Returns:
        str: Base URL (production or development)
    """
    env = os.getenv('FLASK_ENV', 'development')

    if env == 'production':
        # Production - используйте ваш домен
        server_name = os.getenv('SERVER_NAME', 'shohboz.uz')
        return f"https://{server_name}"
    else:
        # Development - localhost
        return "http://127.0.0.1:5000"


def send_verification_email(to_email, token):
    """
    Send verification email for new user registration

    Args:
        to_email (str): User email
        token (str): Verification token
    """
    smtp_server = os.getenv("MAIL_SERVER", os.getenv("SMTP_SERVER"))
    smtp_port = int(os.getenv("MAIL_PORT", os.getenv("SMTP_PORT", 587)))
    login = os.getenv("MAIL_USERNAME", os.getenv("SMTP_LOGIN"))
    password = os.getenv("MAIL_PASSWORD", os.getenv("SMTP_PASSWORD"))

    # ✅ Используем get_base_url() вместо localhost
    base_url = get_base_url()
    link = f"{base_url}/confirm/{token}"

    message = MIMEMultipart("alternative")
    message["Subject"] = "Verify your INHA Student Account"
    message["From"] = login
    message["To"] = to_email

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; background: #f9f9f9; border-radius: 10px;">
          <h2 style="color: #0284c7;">✉️ Welcome to INHA Student Portal!</h2>
          <p>Hello,</p>
          <p>Thank you for registering! Please verify your email address to activate your account.</p>
          <p>Click the button below to complete your registration:</p>
          <div style="text-align: center; margin: 30px 0;">
            <a href="{link}" 
               style="display: inline-block; padding: 14px 30px; background: linear-gradient(135deg, #0284c7, #0277bd); 
                      color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">
              Verify My Email
            </a>
          </div>
          <p style="font-size: 14px; color: #666;">
            Or copy and paste this link into your browser:<br>
            <a href="{link}" style="color: #0284c7;">{link}</a>
          </p>
          <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
          <p style="font-size: 13px; color: #999;">
            ⏱️ This link will expire in <strong>15 minutes</strong>.<br>
            📧 Do not share this link with anyone.<br>
            🔒 If you didn't request this registration, please ignore this email.
          </p>
          <p style="font-size: 13px; color: #999; margin-top: 20px;">
            Best regards,<br>
            <strong></strong>
          </p>
        </div>
      </body>
    </html>
    """
    message.attach(MIMEText(html, "html"))

    # ✅ Поддержка обоих портов (587 TLS и 465 SSL)
    use_tls = os.getenv("MAIL_USE_TLS", "True") == "True"

    context = ssl.create_default_context()

    if smtp_port == 587 or use_tls:
        # TLS (порт 587)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(login, password)
            server.sendmail(login, to_email, message.as_string())
    else:
        # SSL (порт 465)
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(login, password)
            server.sendmail(login, to_email, message.as_string())


def send_password_reset_email(to_email, token):
    """
    Send password reset email with token link

    Args:
        to_email (str): User email
        token (str): Reset token
    """
    smtp_server = os.getenv("MAIL_SERVER", os.getenv("SMTP_SERVER"))
    smtp_port = int(os.getenv("MAIL_PORT", os.getenv("SMTP_PORT", 587)))
    login = os.getenv("MAIL_USERNAME", os.getenv("SMTP_LOGIN"))
    password = os.getenv("MAIL_PASSWORD", os.getenv("SMTP_PASSWORD"))

    # ✅ Используем get_base_url() вместо localhost
    base_url = get_base_url()
    link = f"{base_url}/reset_password/{token}"

    message = MIMEMultipart("alternative")
    message["Subject"] = "Reset Your INHA Student Account Password"
    message["From"] = login
    message["To"] = to_email

    html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; background: #f9f9f9; border-radius: 10px;">
          <h2 style="color: #0284c7;">🔐 Password Reset Request</h2>
          <p>Hello,</p>
          <p>You requested to reset your password for your INHA Student Portal account.</p>
          <p>Click the button below to reset your password:</p>
          <div style="text-align: center; margin: 30px 0;">
            <a href="{link}" 
               style="display: inline-block; padding: 14px 30px; background: linear-gradient(135deg, #0284c7, #0277bd); 
                      color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">
              Reset My Password
            </a>
          </div>
          <p style="font-size: 14px; color: #666;">
            Or copy and paste this link into your browser:<br>
            <a href="{link}" style="color: #0284c7;">{link}</a>
          </p>
          <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
          <p style="font-size: 13px; color: #999;">
            ⏱️ This link will expire in <strong>30 minutes</strong>.<br>
            🔒 If you didn't request this password reset, please ignore this email.<br>
            📧 Do not share this link with anyone.
          </p>
          <p style="font-size: 13px; color: #999; margin-top: 20px;">
            Best regards,<br>
            <strong>INHA Student Portal Team</strong>
          </p>
        </div>
      </body>
    </html>
    """
    message.attach(MIMEText(html, "html"))

    # ✅ Поддержка обоих портов (587 TLS и 465 SSL)
    use_tls = os.getenv("MAIL_USE_TLS", "True") == "True"

    context = ssl.create_default_context()

    if smtp_port == 587 or use_tls:
        # TLS (порт 587)
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(login, password)
            server.sendmail(login, to_email, message.as_string())
    else:
        # SSL (порт 465)
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(login, password)
            server.sendmail(login, to_email, message.as_string())