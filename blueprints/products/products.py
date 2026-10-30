from flask import Blueprint, request, make_response, jsonify
from bson import ObjectId
import uuid
import globals
from decorators import jwt_required, admin_required
from helpers import valid_styles, parse_list, read_paging

products_bp = Blueprint("products_bp", __name__)


def validate_product_form(form, is_new):
    errors = {}

    name = form.get("name", "").strip()
    if name == "" or len(name) > 100:
        errors["name"] = "Name is required (100 characters max)"

    category = form.get("category", "").strip().lower()
    if category not in globals.CATEGORIES:
        errors["category"] = "Must be one of: " + ", ".join(globals.CATEGORIES)

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


# GET products - public search with filters, sorting and paging
@products_bp.route("/api/v1.0/products", methods=["GET"])
def show_all_products():
    errors = {}
    query = {}

    page_num, page_size, paging_error = read_paging()
    if paging_error:
        errors["paging"] = paging_error

    search = request.args.get("q", "").strip()
    if search != "":
        query["$text"] = {"$search": search}

    category = request.args.get("category", "").strip().lower()
    if category != "":
        if category not in globals.CATEGORIES:
            errors["category"] = "Must be one of: " + ", ".join(globals.CATEGORIES)
        else:
            query["category"] = category

    chosen_styles = parse_list(request.args.get("style", ""))
    if chosen_styles:
        known = valid_styles()
        unknown = [style for style in chosen_styles if style not in known]
        if unknown:
            errors["style"] = "Unknown style(s): " + ", ".join(unknown)
        else:
            query["styles"] = {"$in": chosen_styles}

    price_range = {}
    for arg, operator in [("min_price", "$gte"), ("max_price", "$lte")]:
        value = request.args.get(arg, "").strip()
        if value != "":
            try:
                number = float(value)
                if number < 0:
                    errors[arg] = arg + " cannot be negative"
                else:
                    price_range[operator] = number
            except ValueError:
                errors[arg] = arg + " must be a number"
    if "$gte" in price_range and "$lte" in price_range and price_range["$gte"] > price_range["$lte"]:
        errors["price"] = "min_price cannot be more than max_price"
    if price_range:
        query["variants"] = {"$elemMatch": {"price.amount": price_range}}

    min_rating = request.args.get("min_rating", "").strip()
    if min_rating != "":
        try:
            rating = float(min_rating)
            if rating < 0 or rating > 5:
                errors["min_rating"] = "min_rating must be between 0 and 5"
            else:
                query["ratings.average"] = {"$gte": rating}
        except ValueError:
            errors["min_rating"] = "min_rating must be a number"

    sort_options = {
        "price_asc": ("variants.price.amount", 1),
        "price_desc": ("variants.price.amount", -1),
        "rating": ("ratings.average", -1),
        "name": ("name", 1)
    }
    sort_by = request.args.get("sort", "").strip().lower()
    if sort_by != "" and sort_by not in sort_options:
        errors["sort"] = "Must be one of: " + ", ".join(sort_options)

    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    total = globals.products.count_documents(query)
    cursor = globals.products.find(query)
    if sort_by != "":
        field, direction = sort_options[sort_by]
        cursor = cursor.sort(field, direction)
    cursor = cursor.skip(page_size * (page_num - 1)).limit(page_size)

    results = []
    for product in cursor:
        product["_id"] = str(product["_id"])
        results.append(product)

    return make_response(jsonify({
        "total": total,
        "page": page_num,
        "page_size": page_size,
        "results": results
    }), 200)


# GET one product - public
@products_bp.route("/api/v1.0/products/<string:id>", methods=["GET"])
def show_one_product(id):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid product ID"}), 400)

    product = globals.products.find_one({"_id": ObjectId(id)})
    if product is None:
        return make_response(jsonify({"error": "Product not found"}), 404)

    product["_id"] = str(product["_id"])
    return make_response(jsonify(product), 200)


# POST - add a product (admin only)
@products_bp.route("/api/v1.0/products", methods=["POST"])
@jwt_required
@admin_required
def add_product(current_user):
    data, errors = validate_product_form(request.form, is_new=True)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    data["product_id"] = "PRD-" + uuid.uuid4().hex[:8].upper()
    data["ratings"] = {"average": 0, "count": 0, "reviews": []}

    result = globals.products.insert_one(data)
    new_link = "http://localhost:5001/api/v1.0/products/" + str(result.inserted_id)
    return make_response(jsonify({"url": new_link}), 201)


# PUT - edit a product's details (admin only; variants and ratings are kept)
@products_bp.route("/api/v1.0/products/<string:id>", methods=["PUT"])
@jwt_required
@admin_required
def edit_product(id, current_user):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid product ID"}), 400)

    data, errors = validate_product_form(request.form, is_new=False)
    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    result = globals.products.update_one({"_id": ObjectId(id)}, {"$set": data})
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Product not found"}), 404)

    edited_link = "http://localhost:5001/api/v1.0/products/" + id
    return make_response(jsonify({"url": edited_link}), 200)


# DELETE - remove a product (admin only)
@products_bp.route("/api/v1.0/products/<string:id>", methods=["DELETE"])
@jwt_required
@admin_required
def delete_product(id, current_user):
    if not ObjectId.is_valid(id):
        return make_response(jsonify({"error": "Invalid product ID"}), 400)

    result = globals.products.delete_one({"_id": ObjectId(id)})
    if result.deleted_count == 0:
        return make_response(jsonify({"error": "Product not found"}), 404)

    return make_response(jsonify({}), 204)


# GET retailers near a location - public geo query
@products_bp.route("/api/v1.0/retailers/near", methods=["GET"])
def retailers_near():
    errors = {}

    try:
        longitude = float(request.args.get("lng", ""))
        latitude = float(request.args.get("lat", ""))
        if longitude < -180 or longitude > 180 or latitude < -90 or latitude > 90:
            errors["location"] = "lng must be -180 to 180 and lat -90 to 90"
    except ValueError:
        errors["location"] = "lng and lat are required and must be numbers"

    try:
        max_km = float(request.args.get("km", 100))
        if max_km < 1 or max_km > 1000:
            errors["km"] = "km must be between 1 and 1000"
    except ValueError:
        errors["km"] = "km must be a number"

    match = {}
    category = request.args.get("category", "").strip().lower()
    if category != "":
        if category not in globals.CATEGORIES:
            errors["category"] = "Must be one of: " + ", ".join(globals.CATEGORIES)
        else:
            match["category"] = category

    if errors:
        return make_response(jsonify({"errors": errors}), 400)

    pipeline = [
        {"$geoNear": {
            "near": {"type": "Point", "coordinates": [longitude, latitude]},
            "distanceField": "distance_m",
            "maxDistance": max_km * 1000,
            "spherical": True,
            "query": match
        }},
        {"$group": {
            "_id": "$retailer.name",
            "city": {"$first": "$retailer.city"},
            "delivery": {"$first": "$retailer.delivery"},
            "distance_m": {"$min": "$distance_m"},
            "product_count": {"$sum": 1},
            "cheapest_price": {"$min": {"$min": "$variants.price.amount"}}
        }},
        {"$sort": {"distance_m": 1}},
        {"$project": {
            "_id": 0,
            "retailer": "$_id",
            "city": 1,
            "delivery": 1,
            "product_count": 1,
            "cheapest_price": 1,
            "distance_km": {"$round": [{"$divide": ["$distance_m", 1000]}, 1]}
        }}
    ]

    results = list(globals.products.aggregate(pipeline))
    return make_response(jsonify(results), 200)
