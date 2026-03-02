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
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(days=30)
app.config["JWT_TOKEN_LOCATION"] = ["headers"]

db = SQLAlchemy(app)
jwt = JWTManager(app)

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day"]
)

# ==============================
# ASSOCIATION TABLE
# ==============================

group_members = db.Table(
    'group_members',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('groups.id'), primary_key=True)
)

# ==============================
# MODELS
# ==============================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    userName = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phoneNumber = db.Column(db.String(15), unique=True, nullable=False)
    dob = db.Column(db.String(20), nullable=False)
    password = db.Column(db.String(255), nullable=False)

    groups = db.relationship(
        'Group',
        secondary=group_members,
        backref=db.backref('members', lazy='dynamic')
    )


class Group(db.Model):
    __tablename__ = "groups"

    id = db.Column(db.Integer, primary_key=True)
    groupName = db.Column(db.String(100), nullable=False)
    adminId = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    createdAt = db.Column(db.DateTime, default=db.func.now())


with app.app_context():
    db.create_all()

# ==============================
# REGISTER
# ==============================

@app.route("/onechat/signup/vgtueb567", methods=["POST"])
@limiter.limit("5 per minute")
def register():

    data = request.get_json(force=True)

    email = data.get("email", "").lower().strip()
    phone = data.get("phoneNumber", "").strip()

    if User.query.filter_by(email=email).first() or \
       User.query.filter_by(phoneNumber=phone).first():
        return jsonify({"error": "User already exists"}), 409

    hashed = generate_password_hash(data.get("password"))

    new_user = User(
        userName=data.get("userName"),
        email=email,
        phoneNumber=phone,
        dob=data.get("dob"),
        password=hashed
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

    email = data.get("email", "").lower().strip()
    password = data.get("password")

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password, password):
        return jsonify({"error": "Invalid credentials"}), 401

    return jsonify({
        "access_token": create_access_token(identity=str(user.id)),
        "refresh_token": create_refresh_token(identity=str(user.id)),
        "user": {
            "id": user.id,
            "userName": user.userName,
            "email": user.email,
            "phoneNumber": user.phoneNumber
        }
    }), 200


# ==============================
# SYNC CONTACTS
# ==============================

@app.route("/onechat/sync-contacts", methods=["POST"])
@jwt_required()
def sync_contacts():

    current_user_id = int(get_jwt_identity())
    data = request.get_json(force=True)

    phone_numbers = data.get("contacts", [])

    if not isinstance(phone_numbers, list):
        return jsonify({"error": "Contacts must be list"}), 400

    if len(phone_numbers) > 1000:
        return jsonify({"error": "Too many contacts"}), 400

    matched_users = User.query.filter(
        User.phoneNumber.in_(phone_numbers),
        User.id != current_user_id
    ).all()

    result = [{
        "id": u.id,
        "userName": u.userName,
        "phoneNumber": u.phoneNumber
    } for u in matched_users]

    return jsonify({"matched_users": result}), 200


# ==============================
# CREATE GROUP
# ==============================

@app.route("/onechat/create-group", methods=["POST"])
@jwt_required()
def create_group():

    current_user_id = int(get_jwt_identity())
    data = request.get_json(force=True)

    group_name = data.get("groupName")
    member_ids = data.get("members", [])

    if not group_name or not isinstance(member_ids, list):
        return jsonify({"error": "Invalid data"}), 400

    new_group = Group(groupName=group_name, adminId=current_user_id)

    all_member_ids = set(member_ids + [current_user_id])

    members = User.query.filter(User.id.in_(all_member_ids)).all()
    new_group.members.extend(members)

    db.session.add(new_group)
    db.session.commit()

    return jsonify({
        "message": "Group created",
        "groupId": new_group.id
    }), 201

# ==============================
# REFRESH ACCESS TOKEN
# ==============================

@app.route("/onechat/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()

    new_access_token = create_access_token(identity=str(current_user_id))

    return jsonify({
        "access_token": new_access_token
    }), 200

# ==============================
# PROTECTED ROUTE
# ==============================

@app.route("/onechat/profile", methods=["GET"])
@jwt_required()
def profile():
    current_user_id = int(get_jwt_identity())

    user = User.query.get(current_user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        "id": user.id,
        "userName": user.userName,
        "email": user.email,
        "phoneNumber": user.phoneNumber,
        "dob": user.dob
    }), 200


# ==============================
# RUN
# ==============================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
