from flask import Blueprint, request, make_response, jsonify
from bson import ObjectId
import uuid
import globals
from decorators import jwt_required
from helpers import now, valid_styles, parse_list, read_paging, get_design

designs_bp = Blueprint("designs_bp", __name__)


def validate_design_form(form):
    errors = {}

    for field in ["title", "room_type", "styles", "budget"]:
        if form.get(field, "").strip() == "":
            errors[field] = "This field is required"

    if errors:
        return None, errors

    title = form["title"].strip()
    if len(title) > 100:
        errors["title"] = "Title must be 100 characters or fewer"

    room_type = form["room_type"].strip().lower()
    if room_type not in globals.ROOM_TYPES:
        errors["room_type"] = "Must be one of: " + ", ".join(globals.ROOM_TYPES)

    chosen_styles = parse_list(form["styles"])
    known = valid_styles()
    unknown = [style for style in chosen_styles if style not in known]
    if unknown:
        errors["styles"] = "Unknown style(s): " + ", ".join(unknown)
    elif len(chosen_styles) > 3:
        errors["styles"] = "Choose up to 3 styles"

    try:
        budget = float(form["budget"])
        if budget < 100 or budget > 50000:
            errors["budget"] = "Budget must be between 100 and 50000"
    except ValueError:
        errors["budget"] = "Budget must be a number"

    is_flexible = form.get("is_flexible", "false").strip().lower()
    if is_flexible not in ["true", "false"]:
        errors["is_flexible"] = "Must be true or false"

    dimensions = {}
    for side in ["length", "width"]:
        if form.get(side, "").strip() != "":
            try:
                value = float(form[side])
                if value < 1 or value > 20:
                    errors[side] = side.title() + " must be between 1 and 20 metres"
                else:
                    dimensions[side] = round(value, 1)
            except ValueError:
                errors[side] = side.title() + " must be a number"

    if errors:
        return None, errors

    dimensions["unit"] = "m"

    data = {
        "title": title,
        "room": {
            "type": room_type,
            "dimensions": dimensions,
            "notes": form.get("notes", "").strip()
        },
        "preferences": {
            "styles": chosen_styles,
            "budget": {
                "amount": round(budget, 2),
                "currency": "GBP",
                "is_flexible": is_flexible == "true"
            }
        }
    }
    return data, {}


# GET all designs (with paging) - users see their own, admins see all
@designs_bp.route("/api/v1.0/designs", methods=["GET"])
@jwt_required
def show_all_designs(current_user):
    page_num, page_size, paging_error = read_paging()
    if paging_error:
        return make_response(jsonify({"error": paging_error}), 400)

    page_start = page_size * (page_num - 1)

    if current_user["role"] == "admin":
        query = {}
    else:
        query = {"user_id": current_user["user_id"]}

    data_to_return = []
    for design in globals.designs.find(query).skip(page_start).limit(page_size):
        design["_id"] = str(design["_id"])
        data_to_return.append(design)

    return make_response(jsonify(data_to_return), 200)


# GET one design by its _id
@designs_bp.route("/api/v1.0/designs/<string:id>", methods=["GET"])
@jwt_required
def show_one_design(id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    design["_id"] = str(design["_id"])
    return make_response(jsonify(design), 200)


# POST - add a new design for the logged-in user
@designs_bp.route("/api/v1.0/designs", methods=["POST"])
@jwt_required
def add_design(current_user):
    data, errors = validate_design_form(request.form)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    timestamp = now()
    new_design = {
        "design_id": "DSN-" + uuid.uuid4().hex[:8].upper(),
        "user_id": current_user["user_id"],
        "title": data["title"],
        "room": data["room"],
        "original_image": None,
        "preferences": data["preferences"],
        "status": "uploaded",
        "status_history": [{"status": "uploaded", "at": timestamp}],
        "analysis": None,
        "suggestions": [],
        "created_at": timestamp,
        "updated_at": timestamp
    }

    result = globals.designs.insert_one(new_design)
    new_link = "http://localhost:5001/api/v1.0/designs/" + str(result.inserted_id)
    return make_response(jsonify({"url": new_link}), 201)


# PUT - edit an existing design
@designs_bp.route("/api/v1.0/designs/<string:id>", methods=["PUT"])
@jwt_required
def edit_design(id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    data, errors = validate_design_form(request.form)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    globals.designs.update_one(
        {"_id": ObjectId(id)},
        {"$set": {
            "title": data["title"],
            "room": data["room"],
            "preferences": data["preferences"],
            "updated_at": now()
        }}
    )

    edited_link = "http://localhost:5001/api/v1.0/designs/" + id
    return make_response(jsonify({"url": edited_link}), 200)


# DELETE - remove a design
@designs_bp.route("/api/v1.0/designs/<string:id>", methods=["DELETE"])
@jwt_required
def delete_design(id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    globals.designs.delete_one({"_id": ObjectId(id)})
    globals.users.update_many({}, {"$pull": {"saved_designs": design["design_id"]}})

    return make_response(jsonify({}), 204)
