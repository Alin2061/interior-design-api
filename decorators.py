from flask import request, make_response, jsonify
from functools import wraps
import jwt
import globals


def jwt_required(func):
    @wraps(func)
    def jwt_required_wrapper(*args, **kwargs):
        token = request.headers.get("x-access-token")
        if not token:
            return make_response(jsonify({"message": "Token is missing"}), 401)

        try:
            data = jwt.decode(token, globals.secret_key, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return make_response(jsonify({"message": "Token has expired"}), 401)
        except jwt.InvalidTokenError:
            return make_response(jsonify({"message": "Token is invalid"}), 401)

        if globals.blacklist.find_one({"token": token}) is not None:
            return make_response(jsonify({"message": "Token has been cancelled"}), 401)

        kwargs["current_user"] = data
        return func(*args, **kwargs)
    return jwt_required_wrapper


def admin_required(func):
    @wraps(func)
    def admin_required_wrapper(*args, **kwargs):
        if kwargs["current_user"]["role"] != "admin":
            return make_response(jsonify({"message": "Admin access required"}), 403)
        return func(*args, **kwargs)
    return admin_required_wrapper
