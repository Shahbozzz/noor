# INHA Student Platform NOOR🎓

A modern student community platform built for INHA University

## ✨ Features

- **Student Voice** - Faculty-separated discussion boards (SOCIE & SBL) with likes and notifications
- **Friend System** - Send requests, connect with classmates, real-time notifications
- **Smart Profiles** - Photo uploads, inline editing, personalized experience
- **Gender Theming** - Dynamic UI colors (blue for males, pink for females)
- **Real-time Notifications** - Instant updates for all activities

## 🚀 Tech Stack

**Backend**
- Flask (Python)
- PostgreSQL
- Redis (sessions & caching)

**Frontend**
- HTML5, CSS3, JavaScript
- Responsive design

**Deployment**
- Nginx + Gunicorn
- Let's Encrypt SSL
- Cloudflare protection

## 🔒 Security

- CSRF & XSS protection
- Fail2ban integration
- SSH key authentication
- Rate limiting
- Cloudflare WAF

## 🛠️ Setup

1. **Clone the repository**
```bash
git clone https://github.com/Shahbozzz/noor.git
cd noor
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your database and Redis credentials
```

4. **Initialize database**
```bash
python init_db.py
```

5. **Run the application**
```bash
flask run
```

## 📝 Environment Variables
```env
DATABASE_URL=postgresql://user:password@localhost/inha_db
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key
FLASK_ENV=production
```

## 🌐 Production

Test it in **[shohboz.uz](https://shohboz.uz)** serving INHA University students.
---

Built with ❤️ for INHA University students
