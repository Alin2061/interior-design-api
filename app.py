from flask import Flask, make_response, jsonify, request
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime, timezone, timedelta
from functools import wraps
import uuid
import re
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

CATEGORIES = ["furniture", "decor", "lighting", "paint"]


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def valid_styles():
    return [style["name"] for style in styles.find({}, {"_id": 0, "name": 1})]


def parse_list(text):
    return [item.strip().lower() for item in text.split(",") if item.strip()]


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


def admin_required(func):
    @wraps(func)
    def admin_required_wrapper(*args, **kwargs):
        if kwargs["current_user"]["role"] != "admin":
            return make_response(jsonify({"message": "Admin access required"}), 403)
        return func(*args, **kwargs)
    return admin_required_wrapper


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



# GET - log out by cancelling the token
@app.route("/api/v1.0/logout", methods=["GET"])
@jwt_required
def logout(current_user):
    token = request.headers.get("x-access-token")
    blacklist.insert_one({
        "token": token,
        "username": current_user["username"],
        "logged_out_at": now()
    })
    return make_response(jsonify({"message": "Logout successful"}), 200)


# POST - create a new user account
@app.route("/api/v1.0/register", methods=["POST"])
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

    if users.find_one({"username": username}) is not None:
        return make_response(jsonify({"errors": {"username": "Username is already taken"}}), 409)

    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
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
            "created_at": now(),
            "last_login": None
        },
        "saved_preferences": {
            "favourite_styles": [],
            "default_budget": {"amount": 500, "currency": "GBP"}
        },
        "saved_designs": []
    }
    users.insert_one(new_user)
    return make_response(jsonify({"message": "Account created", "username": username}), 201)





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
@jwt_required
def delete_design(id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

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
@jwt_required
def show_all_suggestions(id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    return make_response(jsonify(design["suggestions"]), 200)


# GET one suggestion
@app.route("/api/v1.0/designs/<string:id>/suggestions/<string:sug_id>", methods=["GET"])
@jwt_required
def show_one_suggestion(id, sug_id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    result = designs.find_one(
        {"_id": ObjectId(id), "suggestions.suggestion_id": sug_id},
        {"_id": 0, "suggestions.$": 1}
    )
    if result is None:
        return make_response(jsonify({"error": "Suggestion not found"}), 404)

    return make_response(jsonify(result["suggestions"][0]), 200)


# POST - generate a new suggestion for a design
@app.route("/api/v1.0/designs/<string:id>/suggestions", methods=["POST"])
@jwt_required
def add_suggestion(id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    style = request.form.get("style", "").strip().lower()
    if style == "":
        style = design["preferences"]["styles"][0]
        known = valid_styles()
    if style not in known:
        return make_response(jsonify(
            {"errors": {"style": "Must be one of: " + ", ".join(known)}}), 400)

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
@jwt_required
def edit_suggestion(id, sug_id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

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
@jwt_required
def delete_suggestion(id, sug_id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    result = designs.update_one(
        {"_id": ObjectId(id), "suggestions.suggestion_id": sug_id},
        {"$pull": {"suggestions": {"suggestion_id": sug_id}},
         "$set": {"updated_at": now()}}
    )
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Design or suggestion not found"}), 404)

    return make_response(jsonify({}), 204)

# ---------- Admin: styles ----------

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
@app.route("/api/v1.0/styles", methods=["GET"])
def show_all_styles():
    data_to_return = []
    for style in styles.find({}, {"_id": 0}).sort("name", 1):
        data_to_return.append(style)
    return make_response(jsonify(data_to_return), 200)


# GET one style by name - public
@app.route("/api/v1.0/styles/<string:name>", methods=["GET"])
def show_one_style(name):
    style = styles.find_one({"name": name.lower()}, {"_id": 0})
    if style is None:
        return make_response(jsonify({"error": "Style not found"}), 404)
    return make_response(jsonify(style), 200)


# POST - add a style (admin only)
@app.route("/api/v1.0/styles", methods=["POST"])
@jwt_required
@admin_required
def add_style(current_user):
    data, errors = validate_style_form(request.form)

    name = request.form.get("name", "").strip().lower()
    if not re.fullmatch(r"[a-z]+(-[a-z]+)*", name):
        errors["name"] = "Name must be lowercase letters, optionally joined by hyphens"

    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    if styles.find_one({"name": name}) is not None:
        return make_response(jsonify({"errors": {"name": "Style already exists"}}), 409)

    data["style_id"] = "STY-" + uuid.uuid4().hex[:8].upper()
    data["name"] = name
    data["created_at"] = now()
    styles.insert_one(data)

    new_link = "http://localhost:5001/api/v1.0/styles/" + name
    return make_response(jsonify({"url": new_link}), 201)


# PUT - edit a style (admin only)
@app.route("/api/v1.0/styles/<string:name>", methods=["PUT"])
@jwt_required
@admin_required
def edit_style(name, current_user):
    data, errors = validate_style_form(request.form)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    result = styles.update_one({"name": name.lower()}, {"$set": data})
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Style not found"}), 404)

    edited_link = "http://localhost:5001/api/v1.0/styles/" + name.lower()
    return make_response(jsonify({"url": edited_link}), 200)


# DELETE - remove a style (admin only, only if nothing uses it)
@app.route("/api/v1.0/styles/<string:name>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_style(name, current_user):
    name = name.lower()
    if styles.find_one({"name": name}) is None:
        return make_response(jsonify({"error": "Style not found"}), 404)

    product_count = products.count_documents({"styles": name})
    design_count = designs.count_documents({"preferences.styles": name})
    if product_count > 0 or design_count > 0:
        return make_response(jsonify({
            "error": "Style is still in use",
            "products_using_it": product_count,
            "designs_using_it": design_count
        }), 409)

    styles.delete_one({"name": name})
    return make_response(jsonify({}), 204)


# ---------- Admin: products ----------

def validate_product_form(form, is_new):
    errors = {}

    name = form.get("name", "").strip()
    if name == "" or len(name) > 100:
        errors["name"] = "Name is required (100 characters max)"

    category = form.get("category", "").strip().lower()
    if category not in CATEGORIES:
        errors["category"] = "Must be one of: " + ", ".join(CATEGORIES)

    chosen_styles = parse_list(form.get("styles", ""))
    known = valid_styles()
    unknown = [style for style in chosen_styles if style not in known]
    if len(chosen_styles) == 0:
        errors["styles"] = "Give at least one style"
    elif unknown:
        errors["styles"] = "Unknown style(s): " + ", ".join(unknown)

    retailer_name = form.get("retailer_name", "").strip()
    if retailer_name == "":
        errors["retailer_name"] = "This field is required"

    try:
        longitude = float(form.get("longitude", ""))
        latitude = float(form.get("latitude", ""))
        if longitude < -180 or longitude > 180 or latitude < -90 or latitude > 90:
            errors["location"] = "Longitude must be -180 to 180 and latitude -90 to 90"
    except ValueError:
        errors["location"] = "Longitude and latitude must be numbers"

    try:
        delivery_cost = float(form.get("delivery_cost", "0"))
        if delivery_cost < 0 or delivery_cost > 100:
            errors["delivery_cost"] = "Delivery cost must be between 0 and 100"
    except ValueError:
        errors["delivery_cost"] = "Delivery cost must be a number"

    data = {}
    if not errors:
        data = {
            "name": name,
            "category": category,
            "styles": chosen_styles,
            "retailer": {
                "name": retailer_name,
                "city": form.get("city", "").strip(),
                "location": {"type": "Point", "coordinates": [longitude, latitude]},
                "delivery": {"cost": round(delivery_cost, 2), "days": 3}
            }
        }

    if is_new:
        try:
            price = float(form.get("price", ""))
            if price < 1 or price > 10000:
                errors["price"] = "Price must be between 1 and 10000"
        except ValueError:
            errors["price"] = "Price must be a number"

        try:
            stock = int(form.get("stock", ""))
            if stock < 0 or stock > 1000:
                errors["stock"] = "Stock must be between 0 and 1000"
        except ValueError:
            errors["stock"] = "Stock must be a whole number"

        colour = form.get("colour", "").strip().lower()
        if colour == "":
            errors["colour"] = "This field is required"

        if not errors:
            data["variants"] = [{
                "variant_id": "VAR-" + uuid.uuid4().hex[:8].upper(),
                "colour": colour,
                "material": form.get("material", "").strip().lower(),
                "price": {"amount": round(price, 2), "currency": "GBP"},
                "stock": stock
            }]

    return data, errors


# GET one product - public
@app.route("/api/v1.0/products/<string:id>", methods=["GET"])
def show_one_product(id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid product ID"}), 400)

    product = products.find_one({"_id": ObjectId(id)})
    if product is None:
        return make_response(jsonify({"error": "Product not found"}), 404)

    product["_id"] = str(product["_id"])
    return make_response(jsonify(product), 200)


# POST - add a product (admin only)
@app.route("/api/v1.0/products", methods=["POST"])
@jwt_required
@admin_required
def add_product(current_user):
    data, errors = validate_product_form(request.form, is_new=True)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    data["product_id"] = "PRD-" + uuid.uuid4().hex[:8].upper()
    data["ratings"] = {"average": 0, "count": 0, "reviews": []}

    result = products.insert_one(data)
    new_link = "http://localhost:5001/api/v1.0/products/" + str(result.inserted_id)
    return make_response(jsonify({"url": new_link}), 201)


# PUT - edit a product's details (admin only; variants and ratings are kept)
@app.route("/api/v1.0/products/<string:id>", methods=["PUT"])
@jwt_required
@admin_required
def edit_product(id, current_user):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid product ID"}), 400)

    data, errors = validate_product_form(request.form, is_new=False)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    result = products.update_one({"_id": ObjectId(id)}, {"$set": data})
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Product not found"}), 404)

    edited_link = "http://localhost:5001/api/v1.0/products/" + id
    return make_response(jsonify({"url": edited_link}), 200)


# DELETE - remove a product (admin only)
@app.route("/api/v1.0/products/<string:id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_product(id, current_user):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid product ID"}), 400)

    result = products.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        return make_response(jsonify({"error": "Product not found"}), 404)

    return make_response(jsonify({}), 204)


# ---------- Admin: users ----------

# GET all users without passwords (admin only)
@app.route("/api/v1.0/users", methods=["GET"])
@jwt_required
@admin_required
def show_all_users(current_user):
    data_to_return = []
    for user in users.find({}, {"_id": 0, "password": 0}).sort("user_id", 1):
        data_to_return.append(user)
    return make_response(jsonify(data_to_return), 200)


if __name__ == "__main__":
    app.run(debug=True, port=5001)