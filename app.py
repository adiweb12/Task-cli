import os
from datetime import timedelta
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token,
    create_refresh_token, jwt_required,
    get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
from dotenv import load_dotenv

# ==============================
# LOAD ENV
# ==============================

load_dotenv()

app = Flask(__name__)
CORS(app)

# ==============================
# CONFIGURATION
# ==============================

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_ALGORITHM"] = "HS512"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(minutes=15)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=7)

db = SQLAlchemy(app)
jwt = JWTManager(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"]
)

# ==============================
# DATABASE MODEL
# ==============================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    userName = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phoneNumber = db.Column(db.String(15), nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(255), nullable=False)

# ==============================
# CREATE TABLES
# ==============================

with app.app_context():
    db.create_all()

# ==============================
# PASSWORD VALIDATION
# ==============================

def validate_password(password):
    return (
        len(password) >= 8 and
        any(c.isupper() for c in password) and
        any(c.islower() for c in password) and
        any(c.isdigit() for c in password)
    )

# ==============================
# SIGNUP
# ==============================

@app.route("/onechat/signup/vgtueb567", methods=["POST"])
@limiter.limit("5 per minute")
def register():
    data = request.get_json(force=True)

    userName = data.get("userName")
    email = data.get("email")
    phoneNumber = data.get("phoneNumber")
    dob = data.get("dob")
    password = data.get("password")

    if not all([userName, email, phoneNumber, dob, password]):
        return jsonify({"error": "All fields are required"}), 400

    if not validate_password(password):
        return jsonify({"error": "Password too weak"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    hashed_password = generate_password_hash(password)

    new_user = User(
        userName=userName,
        email=email,
        phoneNumber=phoneNumber,
        dob=dob,
        password=hashed_password
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201

# ==============================
# LOGIN
# ==============================

@app.route("/onechat/login/vdhj67", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    data = request.get_json(force=True)

    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing credentials"}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid credentials"}), 401

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "userName": user.userName,
            "email": user.email
        }
    }), 200

# ==============================
# UPDATE EMAIL
# ==============================

@app.route("/onechat/update-email", methods=["PUT"])
@jwt_required()
def update_email():
    current_user_id = get_jwt_identity()
    data = request.get_json(force=True)

    phoneNumber = data.get("phoneNumber")
    new_email = data.get("newEmail")

    if not phoneNumber or not new_email:
        return jsonify({"error": "Phone number and new email required"}), 400

    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Verify phone matches logged in user
    if user.phoneNumber != phoneNumber:
        return jsonify({"error": "Phone number does not match"}), 403

    # Check if email already taken
    if User.query.filter_by(email=new_email).first():
        return jsonify({"error": "Email already in use"}), 409

    user.email = new_email
    db.session.commit()

    return jsonify({"message": "Email updated successfully"}), 200
    
# ==============================
# UPDATE PASSWORD
# ==============================

@app.route("/onechat/update-password", methods=["PUT"])
@jwt_required()
def update_password():
    current_user_id = get_jwt_identity()
    data = request.get_json(force=True)

    email = data.get("email")
    new_password = data.get("newPassword")

    if not email or not new_password:
        return jsonify({"error": "Email and new password required"}), 400

    if not validate_password(new_password):
        return jsonify({"error": "Weak password"}), 400

    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Verify email matches logged in user
    if user.email != email:
        return jsonify({"error": "Email does not match"}), 403

    hashed_password = generate_password_hash(new_password)
    user.password = hashed_password
    db.session.commit()

    return jsonify({"message": "Password updated successfully"}), 200

# ==============================
# SYNC CONTACTS (SAFE)
# ==============================

@app.route("/onechat/sync-contacts", methods=["POST"])
@jwt_required()
def sync_contacts():
    current_user_id = get_jwt_identity()
    data = request.get_json(force=True)

    phone_numbers = data.get("contacts", [])

    if not isinstance(phone_numbers, list):
        return jsonify({"error": "Contacts must be a list"}), 400

    if not phone_numbers:
        return jsonify({"matched_users": []}), 200

    # Prevent abuse
    if len(phone_numbers) > 1000:
        return jsonify({"error": "Too many contacts"}), 400

    # Normalize numbers (important)
    cleaned_numbers = [
        p.replace(" ", "").replace("-", "").strip()
        for p in phone_numbers
    ]

    matched_users = User.query.filter(
        User.phoneNumber.in_(cleaned_numbers),
        User.id != current_user_id
    ).all()

    result = [
        {
            "id": user.id,
            "userName": user.userName,
            "phoneNumber": user.phoneNumber
        }
        for user in matched_users
    ]

    return jsonify({"matched_users": result}), 200


# ==============================
# REFRESH TOKEN
# ==============================

@app.route("/onechat/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    current_user = get_jwt_identity()
    new_access_token = create_access_token(identity=str(current_user))
    return jsonify({"access_token": new_access_token}), 200

# ==============================
# PROTECTED ROUTE
# ==============================

@app.route("/onechat/protected", methods=["GET"])
@jwt_required()
def protected():
    user_id = get_jwt_identity()
    return jsonify({"message": "Access granted", "user_id": user_id}), 200

# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

