from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import smtplib
import random
import string
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)

# ──────────────── Configuration ────────────────

# Fix for Render's DATABASE_URL (PostgreSQL)
database_url = os.environ.get('DATABASE_URL', 'sqlite:///onechat.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'your-super-secret-jwt-key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)

# Gmail SMTP config
SMTP_EMAIL = os.environ.get('MAIL_USERNAME', 'your-gmail@gmail.com')
SMTP_PASSWORD = os.environ.get('MAIL_PASSWORD', 'your-app-password')

db = SQLAlchemy(app)
jwt = JWTManager(app)

# ──────────────── Models ────────────────

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100))
    is_verified = db.Column(db.Boolean, default=False)
    otp = db.Column(db.String(6))
    otp_expires = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)

class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GroupMember(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# ──────────────── Helpers ────────────────

def send_otp_email(to_email, otp):
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email
        msg['Subject'] = 'OneChat - Email Verification OTP'
        body = f"""
        <html><body>
        <h2>OneChat Email Verification</h2>
        <p>Your OTP code is:</p>
        <h1 style="letter-spacing: 8px; color: #6C63FF;">{otp}</h1>
        <p>This code expires in 10 minutes.</p>
        </body></html>
        """
        msg.attach(MIMEText(body, 'html'))
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def format_message(msg):
    return {
        'id': msg.id,
        'sender_id': msg.sender_id,
        'receiver_id': msg.receiver_id,
        'content': msg.content,
        'timestamp': msg.timestamp.isoformat(),
        'is_read': msg.is_read,
    }

# ──────────────── Auth Routes ────────────────

@app.route('/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    phone = data.get('phone', '').strip()
    password = data.get('password', '')

    if not email or not phone or not password:
        return jsonify({'success': False, 'message': 'All fields required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'success': False, 'message': 'Email already registered'}), 400

    if User.query.filter_by(phone=phone).first():
        return jsonify({'success': False, 'message': 'Phone already registered'}), 400

    otp = generate_otp()
    otp_expires = datetime.utcnow() + timedelta(minutes=10)
    
    user = User(
        email=email,
        phone=phone,
        password_hash=generate_password_hash(password),
        name=email.split('@')[0],
        otp=otp,
        otp_expires=otp_expires,
    )
    db.session.add(user)
    db.session.commit()

    send_otp_email(email, otp)
    return jsonify({'success': True, 'message': 'OTP sent to your email'})

@app.route('/auth/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    otp = data.get('otp', '').strip()

    user = User.query.filter_by(email=email).first()
    if not user or user.otp != otp:
        return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

    if datetime.utcnow() > user.otp_expires:
        return jsonify({'success': False, 'message': 'OTP expired'}), 400

    user.is_verified = True
    user.otp = None
    db.session.commit()
    return jsonify({'success': True, 'message': 'Email verified successfully'})

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

    if not user.is_verified:
        return jsonify({'success': False, 'message': 'Please verify your email first'}), 403

    token = create_access_token(identity=str(user.id))
    return jsonify({
        'success': True,
        'token': token,
        'user_id': user.id,
        'name': user.name,
    })

# ──────────────── Chat Routes ────────────────

@app.route('/chat/list', methods=['GET'])
@jwt_required()
def chat_list():
    me = int(get_jwt_identity())
    sent = db.session.query(Message.receiver_id).filter_by(sender_id=me, is_deleted=False).distinct()
    recv = db.session.query(Message.sender_id).filter_by(receiver_id=me, is_deleted=False).distinct()
    
    partner_ids = {r[0] for r in sent}.union({r[0] for r in recv})
    chats = []
    for pid in partner_ids:
        partner = User.query.get(pid)
        if not partner: continue
        last_msg = Message.query.filter(
            ((Message.sender_id == me) & (Message.receiver_id == pid)) |
            ((Message.sender_id == pid) & (Message.receiver_id == me)),
            Message.is_deleted == False
        ).order_by(Message.timestamp.desc()).first()
        
        chats.append({
            'user_id': pid,
            'name': partner.name,
            'last_message': last_msg.content if last_msg else '',
            'last_time': last_msg.timestamp.isoformat() if last_msg else datetime.utcnow().isoformat(),
        })
    return jsonify({'success': True, 'chats': chats})

@app.route('/chat/messages/<int:other_id>', methods=['GET'])
@jwt_required()
def get_messages(other_id):
    me = int(get_jwt_identity())
    messages = Message.query.filter(
        ((Message.sender_id == me) & (Message.receiver_id == other_id)) |
        ((Message.sender_id == other_id) & (Message.receiver_id == me)),
        Message.is_deleted == False
    ).order_by(Message.timestamp.asc()).all()
    return jsonify({'success': True, 'messages': [format_message(m) for m in messages]})

@app.route('/chat/send', methods=['POST'])
@jwt_required()
def send_message():
    me = int(get_jwt_identity())
    data = request.get_json()
    msg = Message(sender_id=me, receiver_id=int(data.get('receiver_id')), content=data.get('content'))
    db.session.add(msg)
    db.session.commit()
    return jsonify({'success': True, 'message': format_message(msg)})

# ──────────────── Initialization ────────────────

# This runs on BOTH Gunicorn (Render) and local Python
# It ensures the PostgreSQL tables exist before the first request
with app.app_context():
    db.create_all()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
