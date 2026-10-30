from flask import Blueprint, request, make_response, jsonify
from bson import ObjectId
import uuid
import random
import globals
from decorators import jwt_required
from helpers import now, valid_styles, get_design

suggestions_bp = Blueprint("suggestions_bp", __name__)


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

    for product in globals.products.aggregate(pipeline):
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

    style_doc = globals.styles.find_one({"name": style})
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
@suggestions_bp.route("/api/v1.0/designs/<string:id>/suggestions", methods=["GET"])
@jwt_required
def show_all_suggestions(id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    return make_response(jsonify(design["suggestions"]), 200)


# GET one suggestion
@suggestions_bp.route("/api/v1.0/designs/<string:id>/suggestions/<string:sug_id>", methods=["GET"])
@jwt_required
def show_one_suggestion(id, sug_id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    result = globals.designs.find_one(
        {"_id": ObjectId(id), "suggestions.suggestion_id": sug_id},
        {"_id": 0, "suggestions.$": 1}
    )
    if result is None:
        return make_response(jsonify({"error": "Suggestion not found"}), 404)

    return make_response(jsonify(result["suggestions"][0]), 200)


# POST - generate a new suggestion for a design
@suggestions_bp.route("/api/v1.0/designs/<string:id>/suggestions", methods=["POST"])
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

    globals.designs.update_one(
        {"_id": ObjectId(id)},
        {"$push": {"suggestions": suggestion}, "$set": {"updated_at": now()}}
    )

    new_link = ("http://localhost:5001/api/v1.0/designs/" + id
                + "/suggestions/" + suggestion["suggestion_id"])
    return make_response(jsonify({"url": new_link}), 201)


# PUT - give feedback on a suggestion
@suggestions_bp.route("/api/v1.0/designs/<string:id>/suggestions/<string:sug_id>", methods=["PUT"])
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

    result = globals.designs.update_one(
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
        return make_response(jsonify({"error": "Suggestion not found"}), 404)

    edited_link = ("http://localhost:5001/api/v1.0/designs/" + id
                   + "/suggestions/" + sug_id)
    return make_response(jsonify({"url": edited_link}), 200)


# DELETE - remove a suggestion
@suggestions_bp.route("/api/v1.0/designs/<string:id>/suggestions/<string:sug_id>", methods=["DELETE"])
@jwt_required
def delete_suggestion(id, sug_id, current_user):
    design, error = get_design(id, current_user)
    if error:
        return error

    result = globals.designs.update_one(
        {"_id": ObjectId(id), "suggestions.suggestion_id": sug_id},
        {"$pull": {"suggestions": {"suggestion_id": sug_id}},
         "$set": {"updated_at": now()}}
    )
    if result.matched_count == 0:
        return make_response(jsonify({"error": "Suggestion not found"}), 404)

    return make_response(jsonify({}), 204)
