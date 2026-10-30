from flask import Blueprint, request, make_response, jsonify
import uuid
import re
import globals
from decorators import jwt_required, admin_required
from helpers import now, parse_list

styles_bp = Blueprint("styles_bp", __name__)


def validate_style_form(form):
    errors = {}

    description = form.get("description", "").strip()
    if description == "" or len(description) > 300:
        errors["description"] = "Description is required (300 characters max)"

    key_features = parse_list(form.get("key_features", ""))
    if len(key_features) == 0:
        errors["key_features"] = "Give at least one key feature, separated by commas"

    materials = parse_list(form.get("materials", ""))
    if len(materials) == 0:
        errors["materials"] = "Give at least one material, separated by commas"

    palette = []
    for pair in form.get("colours", "").split(","):
        if pair.strip() == "":
            continue
        if ":" not in pair:
            errors["colours"] = "Use the format name:#HEX, for example white:#FFFFFF"
            break
        name, hex_code = pair.split(":", 1)
        hex_code = hex_code.strip().upper()
        if not re.fullmatch(r"#[0-9A-F]{6}", hex_code):
            errors["colours"] = hex_code + " is not a valid hex colour like #1F2A44"
            break
        palette.append({"name": name.strip().lower(), "hex": hex_code})

    if "colours" not in errors and len(palette) < 3:
        errors["colours"] = "Give at least 3 colours (walls, floor, accent)"

    data = {
        "description": description,
        "key_features": key_features,
        "materials": materials,
        "colour_palette": palette
    }
    return data, errors


# GET all styles - public
@styles_bp.route("/api/v1.0/styles", methods=["GET"])
def show_all_styles():
    data_to_return = []
    for style in globals.styles.find({}, {"_id": 0}).sort("name", 1):
        data_to_return.append(style)
    return make_response(jsonify(data_to_return), 200)


# GET one style by name - public
@styles_bp.route("/api/v1.0/styles/<string:name>", methods=["GET"])
def show_one_style(name):
    style = globals.styles.find_one({"name": name.lower()}, {"_id": 0})
    if style is None:
        return make_response(jsonify({"error": "Style not found"}), 404)
    return make_response(jsonify(style), 200)


# POST - add a style (admin only)
@styles_bp.route("/api/v1.0/styles", methods=["POST"])
@jwt_required
@admin_required
def add_style(current_user):
    data, errors = validate_style_form(request.form)

    name = request.form.get("name", "").strip().lower()
    if not re.fullmatch(r"[a-z]+(-[a-z]+)*", name):
        errors["name"] = "Name must be lowercase letters, optionally joined by hyphens"

    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    if globals.styles.find_one({"name": name}) is not None:
        return make_response(jsonify({"errors": {"name": "Style already exists"}}), 409)

    data["style_id"] = "STY-" + uuid.uuid4().hex[:8].upper()
    data["name"] = name
    data["created_at"] = now()
    globals.styles.insert_one(data)

    new_link = "http://localhost:5001/api/v1.0/styles/" + name
    return make_response(jsonify({"url": new_link}), 201)


# PUT - edit a style (admin only)
@styles_bp.route("/api/v1.0/styles/<string:name>", methods=["PUT"])
@jwt_required
@admin_required
def edit_style(name, current_user):
    data, errors = validate_style_form(request.form)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    result = globals.styles.update_one({"name": name.lower()}, {"$set": data})
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Style not found"}), 404)

    edited_link = "http://localhost:5001/api/v1.0/styles/" + name.lower()
    return make_response(jsonify({"url": edited_link}), 200)


# DELETE - remove a style (admin only, only if nothing uses it)
@styles_bp.route("/api/v1.0/styles/<string:name>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_style(name, current_user):
    name = name.lower()
    if globals.styles.find_one({"name": name}) is None:
        return make_response(jsonify({"error": "Style not found"}), 404)

    product_count = globals.products.count_documents({"styles": name})
    design_count = globals.designs.count_documents({"preferences.styles": name})
    if product_count > 0 or design_count > 0:
        return make_response(jsonify({
            "error": "Style is still in use",
            "products_using_it": product_count,
            "designs_using_it": design_count
        }), 409)

    globals.styles.delete_one({"name": name})
    return make_response(jsonify({}), 204)
