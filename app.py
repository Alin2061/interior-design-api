from flask import Flask, make_response, jsonify, request
from pymongo import MongoClient
from bson import ObjectId

from datetime import datetime, timezone
import uuid

client = MongoClient("mongodb://localhost:27017")
db = client.interiorDB
designs = db.designs

users = db.users

app = Flask(__name__)


ROOM_TYPES = ["bedroom", "living room", "office", "kitchen"]

STYLES = ["modern", "minimalist", "scandinavian", "industrial",
          "bohemian", "mid-century", "traditional", "coastal"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
    if room_type not in ROOM_TYPES:
        errors["room_type"] = "Must be one of: " + ", ".join(ROOM_TYPES)

    styles = [style.strip().lower() for style in form["styles"].split(",") if style.strip()]
    unknown = [style for style in styles if style not in STYLES]
    if unknown:
        errors["styles"] = "Unknown style(s): " + ", ".join(unknown)
    elif len(styles) > 3:
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
            "styles": styles,
            "budget": {
                "amount": round(budget, 2),
                "currency": "GBP",
                "is_flexible": is_flexible == "true"
            }
        }
    }
    return data, {}


@app.route("/", methods=["GET"])
def index():
    return make_response("<h1>Interior Design API</h1>", 200)


# GET all designs (with paging)
@app.route("/api/v1.0/designs", methods=["GET"])
def show_all_designs():
    page_num, page_size = 1, 10

    try:
        if request.args.get("pn"):
            page_num = int(request.args.get("pn"))
        if request.args.get("ps"):
            page_size = int(request.args.get("ps"))
    except ValueError:
        return make_response(jsonify({"error": "pn and ps must be whole numbers"}), 400)

    if page_num < 1 or page_size < 1 or page_size > 50:
        return make_response(jsonify(
            {"error": "pn must be 1 or more and ps must be between 1 and 50"}), 400)

    page_start = page_size * (page_num - 1)

    data_to_return = []
    for design in designs.find().skip(page_start).limit(page_size):
        design["_id"] = str(design["_id"])
        data_to_return.append(design)

    return make_response(jsonify(data_to_return), 200)


# GET one design by its _id
@app.route("/api/v1.0/designs/<string:id>", methods=["GET"])
def show_one_design(id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid design ID"}), 400)

    design = designs.find_one({"_id": ObjectId(id)})
    if design is None:
        return make_response(jsonify({"error": "Design not found"}), 404)

    design["_id"] = str(design["_id"])
    return make_response(jsonify(design), 200)



# POST - add a new design
@app.route("/api/v1.0/designs", methods=["POST"])
def add_design():
    data, errors = validate_design_form(request.form)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    # TEMPORARY: user_id comes from the form until we add login tokens
    user_id = request.form.get("user_id", "").strip()
    if users.find_one({"user_id": user_id}) is None:
        return make_response(jsonify({"errors": {"user_id": "User not found"}}), 400)

    timestamp = now()
    new_design = {
        "design_id": "DSN-" + uuid.uuid4().hex[:8].upper(),
        "user_id": user_id,
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

    result = designs.insert_one(new_design)
    new_link = "http://localhost:5001/api/v1.0/designs/" + str(result.inserted_id)
    return make_response(jsonify({"url": new_link}), 201)


# PUT - edit an existing design
@app.route("/api/v1.0/designs/<string:id>", methods=["PUT"])
def edit_design(id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid design ID"}), 400)

    data, errors = validate_design_form(request.form)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    result = designs.update_one(
        {"_id": ObjectId(id)},
        {"$set": {
            "title": data["title"],
            "room": data["room"],
            "preferences": data["preferences"],
            "updated_at": now()
        }}
    )
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Design not found"}), 404)

    edited_link = "http://localhost:5001/api/v1.0/designs/" + id
    return make_response(jsonify({"url": edited_link}), 200)


# DELETE - remove a design
@app.route("/api/v1.0/designs/<string:id>", methods=["DELETE"])
def delete_design(id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid design ID"}), 400)

    design = designs.find_one({"_id": ObjectId(id)})
    if design is None:
        return make_response(jsonify({"error": "Design not found"}), 404)

    designs.delete_one({"_id": ObjectId(id)})
    users.update_many({}, {"$pull": {"saved_designs": design["design_id"]}})

    return make_response(jsonify({}), 204)

if __name__ == "__main__":
    app.run(debug=True, port=5001)