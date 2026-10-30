from flask import Blueprint, request, make_response, jsonify
from datetime import datetime, timezone, timedelta
import uuid
import jwt
import bcrypt
import globals
from decorators import jwt_required, admin_required
from helpers import now

auth_bp = Blueprint("auth_bp", __name__)


# POST - create a new user account
@auth_bp.route("/api/v1.0/register", methods=["POST"])
def register():
    errors = {}

    username = request.form.get("username", "").strip().lower()
    if len(username) < 3 or len(username) > 20 or not username.isalnum():
        errors["username"] = "Username must be 3-20 letters or numbers"

    password = request.form.get("password", "")
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"

    name = request.form.get("name", "").strip()
    if name == "":
        errors["name"] = "This field is required"

    email = request.form.get("email", "").strip().lower()
    if "@" not in email or "." not in email:
        errors["email"] = "Enter a valid email address"

    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    if globals.users.find_one({"username": username}) is not None:
        return make_response(jsonify({"errors": {"username": "Username is already taken"}}), 409)

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    timestamp = now()
    new_user = {
        "user_id": "USR-" + uuid.uuid4().hex[:8].upper(),
        "username": username,
        "password": hashed.decode("utf-8"),
        "profile": {
            "name": name,
            "email": email,
            "address": {
                "city": request.form.get("city", "").strip(),
                "postcode": request.form.get("postcode", "").strip().upper(),
                "country": "United Kingdom"
            }
        },
        "account": {
            "role": "user",
            "created_at": timestamp,
            "last_login": None
        },
        "saved_preferences": {
            "favourite_styles": [],
            "default_budget": {"amount": 500, "currency": "GBP"}
        },
        "saved_designs": []
    }
    globals.users.insert_one(new_user)
    return make_response(jsonify({"message": "Account created", "username": username}), 201)


# GET - log in with Basic Auth and receive a token
@auth_bp.route("/api/v1.0/login", methods=["GET"])
def login():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return make_response(jsonify({"message": "Username and password required"}), 401,
                             {"WWW-Authenticate": 'Basic realm="Login Required"'})

    user = globals.users.find_one({"username": auth.username.lower()})
    if user is None or not bcrypt.checkpw(auth.password.encode("utf-8"),
                                          user["password"].encode("utf-8")):
        return make_response(jsonify({"message": "Wrong username or password"}), 401,
                             {"WWW-Authenticate": 'Basic realm="Login Required"'})

    token = jwt.encode({
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["account"]["role"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
    }, globals.secret_key, algorithm="HS256")

    globals.users.update_one({"_id": user["_id"]}, {"$set": {"account.last_login": now()}})
    return make_response(jsonify({"token": token}), 200)


# GET - log out by cancelling the token
@auth_bp.route("/api/v1.0/logout", methods=["GET"])
@jwt_required
def logout(current_user):
    token = request.headers.get("x-access-token")
    globals.blacklist.insert_one({
        "token": token,
        "username": current_user["username"],
        "logged_out_at": now()
    })
    return make_response(jsonify({"message": "Logout successful"}), 200)


# GET all users without passwords (admin only)
@auth_bp.route("/api/v1.0/users", methods=["GET"])
@jwt_required
@admin_required
def show_all_users(current_user):
    data_to_return = []
    for user in globals.users.find({}, {"_id": 0, "password": 0}).sort("user_id", 1):
        data_to_return.append(user)
    return make_response(jsonify(data_to_return), 200)
