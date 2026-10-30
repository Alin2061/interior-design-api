from flask import request, make_response, jsonify
from bson import ObjectId
from datetime import datetime, timezone
import globals


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def valid_styles():
    return [style["name"] for style in globals.styles.find({}, {"_id": 0, "name": 1})]


def parse_list(text):
    return [item.strip().lower() for item in text.split(",") if item.strip()]


def read_paging(default_size=10):
    try:
        page_num = int(request.args.get("pn", 1))
        page_size = int(request.args.get("ps", default_size))
    except ValueError:
        return None, None, "pn and ps must be whole numbers"

    if page_num < 1 or page_size < 1 or page_size > 50:
        return None, None, "pn must be 1 or more and ps must be between 1 and 50"

    return page_num, page_size, None


def get_design(id, current_user):
    if not ObjectId.is_valid(id):
        return None, make_response(jsonify({"error": "Invalid design ID"}), 400)

    design = globals.designs.find_one({"_id": ObjectId(id)})
    if design is None:
        return None, make_response(jsonify({"error": "Design not found"}), 404)

    if current_user["role"] != "admin" and design["user_id"] != current_user["user_id"]:
        return None, make_response(jsonify({"error": "You do not have access to this design"}), 403)

    return design, None
