from flask import Flask, make_response, jsonify, request
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from functools import wraps
import random

import jwt
import bcrypt

client = MongoClient("mongodb://localhost:27017")
db = client.interiorDB
designs = db.designs
users = db.users
products = db.products
styles = db.styles

blacklist = db.blacklist

app = Flask(__name__)

app.config["SECRET_KEY"] = "com661-interior-design-api-secret-key-2026"

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

def jwt_required(func):
    @wraps(func)
    def jwt_required_wrapper(*args, **kwargs):
        token = request.headers.get("x-access-token")
        if not token:
            return make_response(jsonify({"message": "Token is missing"}), 401)

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return make_response(jsonify({"message": "Token has expired"}), 401)
        except jwt.InvalidTokenError:
            return make_response(jsonify({"message": "Token is invalid"}), 401)

        if blacklist.find_one({"token": token}) is not None:
            return make_response(jsonify({"message": "Token has been cancelled"}), 401)

        kwargs["current_user"] = data
        return func(*args, **kwargs)
    return jwt_required_wrapper


def get_design(id, current_user):
    if not ObjectId.is_valid(id):
        return None, make_response(jsonify({"error": "Invalid design ID"}), 400)

    design = designs.find_one({"_id": ObjectId(id)})
    if design is None:
        return None, make_response(jsonify({"error": "Design not found"}), 404)

    if current_user["role"] != "admin" and design["user_id"] != current_user["user_id"]:
        return None, make_response(jsonify({"error": "You do not have access to this design"}), 403)

    return design, None


# GET - log in with Basic Auth and receive a token



@app.route("/api/v1.0/login", methods=["GET"])
def login():
    auth = request.authorization
    if not auth or not auth.username or not auth.password:
        return make_response(jsonify({"message": "Username and password required"}), 401,
                             {"WWW-Authenticate": 'Basic realm="Login Required"'})

    user = users.find_one({"username": auth.username.lower()})
    if user is None or not bcrypt.checkpw(auth.password.encode("utf-8"),
                                          user["password"].encode("utf-8")):
        return make_response(jsonify({"message": "Wrong username or password"}), 401,
                             {"WWW-Authenticate": 'Basic realm="Login Required"'})

    token = jwt.encode({
        "user_id": user["user_id"],
        "username": user["username"],
        "role": user["account"]["role"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
    }, app.config["SECRET_KEY"], algorithm="HS256")

    users.update_one({"_id": user["_id"]}, {"$set": {"account.last_login": now()}})
    return make_response(jsonify({"token": token}), 200)




@app.route("/", methods=["GET"])
def index():
    return make_response("<h1>Interior Design API</h1>", 200)


# GET all designs (with paging) - users see their own, admins see all
@app.route("/api/v1.0/designs", methods=["GET"])
@jwt_required
def show_all_designs(current_user):
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

    if current_user["role"] == "admin":
        query = {}
    else:
        query = {"user_id": current_user["user_id"]}

    data_to_return = []
    for design in designs.find(query).skip(page_start).limit(page_size):
        design["_id"] = str(design["_id"])
        data_to_return.append(design)

    return make_response(jsonify(data_to_return), 200)


# GET one design by its _id
@app.route("/api/v1.0/designs/<string:id>", methods=["GET"])
@jwt_required
def show_one_design(id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

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
@jwt_required
def edit_design(current_user, id):
    design, error = get_design(id, current_user)
    if error:
        return error

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


# ---------- Suggestions (sub-documents of a design) ----------

def build_suggestion(design, style):
    budget = design["preferences"]["budget"]
    if budget["is_flexible"]:
        limit = budget["amount"] * 1.1
    else:
        limit = budget["amount"]

    if design.get("original_image"):
        resolution = design["original_image"]["resolution"]
    else:
        resolution = {"width": 3024, "height": 4032}

    pipeline = [
        {"$match": {"styles": style}},
        {"$sample": {"size": 40}}
    ]

    items = []
    costs = {"furniture": 0, "decor": 0, "lighting": 0, "paint": 0}
    total = 0
    has_paint = False

    for product in products.aggregate(pipeline):
        if len(items) == 5:
            break
        if product["category"] == "paint" and has_paint:
            continue

        variant = random.choice(product["variants"])
        price = variant["price"]["amount"]
        if total + price > limit:
            continue

        if product["category"] == "paint":
            has_paint = True

        items.append({
            "product_id": product["product_id"],
            "variant_id": variant["variant_id"],
            "name": product["name"],
            "category": product["category"],
            "price": {"amount": price, "currency": "GBP"},
            "placement": {
                "x": random.randint(0, resolution["width"]),
                "y": random.randint(0, resolution["height"]),
                "rotation": random.choice([0, 90, 180, 270])
            }
        })
        costs[product["category"]] += price
        total += price

    style_doc = styles.find_one({"name": style})
    colour_scheme = []
    for area, colour in zip(["walls", "floor", "accent"], style_doc["colour_palette"]):
        colour_scheme.append({"area": area, "name": colour["name"], "hex": colour["hex"]})

    suggestion_id = "SUG-" + uuid.uuid4().hex[:8].upper()
    return {
        "suggestion_id": suggestion_id,
        "style": style,
        "preview_image": {
            "url": "https://storage.example.com/previews/" + design["design_id"].lower()
                   + "-" + suggestion_id.lower() + ".png",
            "generated_at": now()
        },
        "colour_scheme": colour_scheme,
        "items": items,
        "cost_summary": {
            "furniture": round(costs["furniture"], 2),
            "decor": round(costs["decor"], 2),
            "lighting": round(costs["lighting"], 2),
            "paint": round(costs["paint"], 2),
            "total": round(total, 2)
        },
        "feedback": {"rating": None, "comment": "", "is_favourite": False}
    }


# GET all suggestions for one design
@app.route("/api/v1.0/designs/<string:id>/suggestions", methods=["GET"])
def show_all_suggestions(id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid design ID"}), 400)

    design = designs.find_one({"_id": ObjectId(id)}, {"_id": 0, "suggestions": 1})
    if design is None:
        return make_response(jsonify({"error": "Design not found"}), 404)

    return make_response(jsonify(design["suggestions"]), 200)


# GET one suggestion
@app.route("/api/v1.0/designs/<string:id>/suggestions/<string:sug_id>", methods=["GET"])
def show_one_suggestion(id, sug_id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid design ID"}), 400)

    design = designs.find_one(
        {"_id": ObjectId(id), "suggestions.suggestion_id": sug_id},
        {"_id": 0, "suggestions.$": 1}
    )
    if design is None:
        return make_response(jsonify({"error": "Design or suggestion not found"}), 404)

    return make_response(jsonify(design["suggestions"][0]), 200)


# POST - generate a new suggestion for a design
@app.route("/api/v1.0/designs/<string:id>/suggestions", methods=["POST"])
def add_suggestion(id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid design ID"}), 400)

    design = designs.find_one({"_id": ObjectId(id)})
    if design is None:
        return make_response(jsonify({"error": "Design not found"}), 404)

    style = request.form.get("style", "").strip().lower()
    if style == "":
        style = design["preferences"]["styles"][0]
    if style not in STYLES:
        return make_response(jsonify(
            {"errors": {"style": "Must be one of: " + ", ".join(STYLES)}}), 400)

    if len(design["suggestions"]) >= 5:
        return make_response(jsonify(
            {"error": "A design can have at most 5 suggestions"}), 409)

    suggestion = build_suggestion(design, style)
    if len(suggestion["items"]) == 0:
        return make_response(jsonify(
            {"error": "No " + style + " products fit this budget"}), 422)

    designs.update_one(
        {"_id": ObjectId(id)},
        {"$push": {"suggestions": suggestion}, "$set": {"updated_at": now()}}
    )

    new_link = ("http://localhost:5001/api/v1.0/designs/" + id
                + "/suggestions/" + suggestion["suggestion_id"])
    return make_response(jsonify({"url": new_link}), 201)


# PUT - give feedback on a suggestion
@app.route("/api/v1.0/designs/<string:id>/suggestions/<string:sug_id>", methods=["PUT"])
def edit_suggestion(id, sug_id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid design ID"}), 400)

    errors = {}

    try:
        rating = int(request.form.get("rating", ""))
        if rating < 1 or rating > 5:
            errors["rating"] = "Rating must be between 1 and 5"
    except ValueError:
        errors["rating"] = "Rating must be a whole number"

    comment = request.form.get("comment", "").strip()
    if len(comment) > 300:
        errors["comment"] = "Comment must be 300 characters or fewer"

    is_favourite = request.form.get("is_favourite", "false").strip().lower()
    if is_favourite not in ["true", "false"]:
        errors["is_favourite"] = "Must be true or false"

    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    result = designs.update_one(
        {"_id": ObjectId(id), "suggestions.suggestion_id": sug_id},
        {"$set": {
            "suggestions.$.feedback": {
                "rating": rating,
                "comment": comment,
                "is_favourite": is_favourite == "true"
            },
            "updated_at": now()
        }}
    )
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Design or suggestion not found"}), 404)

    edited_link = ("http://localhost:5001/api/v1.0/designs/" + id
                   + "/suggestions/" + sug_id)
    return make_response(jsonify({"url": edited_link}), 200)


# DELETE - remove a suggestion
@app.route("/api/v1.0/designs/<string:id>/suggestions/<string:sug_id>", methods=["DELETE"])
def delete_suggestion(id, sug_id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid design ID"}), 400)

    result = designs.update_one(
        {"_id": ObjectId(id), "suggestions.suggestion_id": sug_id},
        {"$pull": {"suggestions": {"suggestion_id": sug_id}},
         "$set": {"updated_at": now()}}
    )
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Design or suggestion not found"}), 404)

    return make_response(jsonify({}), 204)


if __name__ == "__main__":
    app.run(debug=True, port=5001)