import os
import random
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
from sqlalchemy import text
from dotenv import load_dotenv
from models import db, User

load_dotenv()

app = Flask(__name__)
CORS(app)

# ----------------------------
# DATABASE CONFIG
# ----------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL + "?sslmode=require"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)
bcrypt = Bcrypt(app)

# ----------------------------
# EMAIL CONFIG
# ----------------------------
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get("EMAIL_USER")
app.config['MAIL_PASSWORD'] = os.environ.get("EMAIL_PASS")

mail = Mail(app)

# -------------------------------------------------------
# SAFE AUTO MIGRATION (NO SHELL REQUIRED)
# -------------------------------------------------------
def safe_auto_migrate():
    with app.app_context():
        db.create_all()

        columns_needed = {
            "phone": "VARCHAR(20)",
            "otp_code": "VARCHAR(6)",
            "otp_expiry": "TIMESTAMP",
            "is_verified": "BOOLEAN DEFAULT FALSE"
        }

        result = db.session.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name='user'")
        )

        existing_columns = [row[0] for row in result]

        for column, definition in columns_needed.items():
            if column not in existing_columns:
                db.session.execute(
                    text(f'ALTER TABLE "user" ADD COLUMN {column} {definition}')
                )
                print(f"Added column: {column}")

        db.session.commit()


# -------------------------------------------------------
# ROUTES
# -------------------------------------------------------

@app.route("/")
def home():
    return jsonify({"status": "Chat backend running 🔥"})


# ----------------- SIGNUP REQUEST -----------------------
@app.route("/signup-request", methods=["POST"])
def signup_request():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")
    phone = data.get("phone")

    if not email or not password:
        return jsonify({"message": "Missing fields"}), 400

    user = User.query.filter_by(email=email).first()

    if user and user.is_verified:
        return jsonify({"message": "User already exists"}), 409

    otp = str(random.randint(100000, 999999))
    expiry = datetime.utcnow() + timedelta(minutes=10)
    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")

    if not user:
        user = User(
            email=email,
            phone=phone,
            password=hashed_pw,
            otp_code=otp,
            otp_expiry=expiry,
            is_verified=False
        )
        db.session.add(user)
    else:
        user.otp_code = otp
        user.otp_expiry = expiry

    db.session.commit()

    send_otp_email(email, otp)

    return jsonify({"message": "OTP sent successfully"}), 200


# ----------------- VERIFY OTP -----------------------
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    data = request.get_json()

    email = data.get("email")
    otp = data.get("otp")

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({"message": "User not found"}), 404

    if user.otp_code != otp:
        return jsonify({"message": "Invalid OTP"}), 400

    if datetime.utcnow() > user.otp_expiry:
        return jsonify({"message": "OTP expired"}), 400

    user.is_verified = True
    user.otp_code = None
    user.otp_expiry = None

    db.session.commit()

    return jsonify({"message": "Account verified successfully"}), 200


# -------------------------------------------------------
# PROFESSIONAL OTP EMAIL TEMPLATE
# -------------------------------------------------------
def send_otp_email(to_email, otp):
    html_content = f"""
    <html>
    <body style="margin:0;padding:0;background:#f4f6f8;font-family:Arial;">
        <div style="max-width:600px;margin:40px auto;background:white;padding:40px;border-radius:12px;">
            
            <h2 style="color:#075E54;text-align:center;">
                ChatApp Email Verification
            </h2>

            <p style="font-size:16px;color:#333;">
                Hello,
            </p>

            <p style="font-size:16px;color:#333;">
                Thank you for creating an account. 
                Please use the verification code below:
            </p>

            <div style="
                margin:30px 0;
                text-align:center;
                font-size:36px;
                font-weight:bold;
                letter-spacing:8px;
                color:#25D366;
            ">
                {otp}
            </div>

            <p style="font-size:14px;color:#666;">
                This code will expire in 10 minutes.
            </p>

            <hr style="margin:30px 0;">

            <p style="font-size:12px;color:#aaa;text-align:center;">
                If you did not request this email, you can safely ignore it.
                <br><br>
                © 2026 ChatApp. All rights reserved.
            </p>
        </div>
    </body>
    </html>
    """

    msg = Message(
        subject="Your ChatApp Verification Code",
        sender=app.config['MAIL_USERNAME'],
        recipients=[to_email],
        html=html_content
    )

    mail.send(msg)


# -------------------------------------------------------
# START APP
# -------------------------------------------------------
with app.app_context():
    safe_auto_migrate()

if __name__ == "__main__":
    app.run()
