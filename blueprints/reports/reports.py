from flask import Blueprint, request, make_response, jsonify
import globals
from decorators import jwt_required, admin_required

reports_bp = Blueprint("reports_bp", __name__)


# GET style popularity - how many designs choose each style, and their average budget
@reports_bp.route("/api/v1.0/reports/styles", methods=["GET"])
@jwt_required
@admin_required
def report_styles(current_user):
    pipeline = [
        {"$unwind": "$preferences.styles"},
        {"$group": {
            "_id": "$preferences.styles",
            "design_count": {"$sum": 1},
            "average_budget": {"$avg": "$preferences.budget.amount"}
        }},
        {"$sort": {"design_count": -1}},
        {"$project": {
            "_id": 0,
            "style": "$_id",
            "design_count": 1,
            "average_budget": {"$round": ["$average_budget", 2]}
        }}
    ]
    return make_response(jsonify(list(globals.designs.aggregate(pipeline))), 200)


# GET suggestion spending - average cost and rating of suggestions for each style
@reports_bp.route("/api/v1.0/reports/spending", methods=["GET"])
@jwt_required
@admin_required
def report_spending(current_user):
    pipeline = [
        {"$unwind": "$suggestions"},
        {"$group": {
            "_id": "$suggestions.style",
            "suggestion_count": {"$sum": 1},
            "average_total": {"$avg": "$suggestions.cost_summary.total"},
            "average_rating": {"$avg": "$suggestions.feedback.rating"},
            "highest_total": {"$max": "$suggestions.cost_summary.total"}
        }},
        {"$sort": {"average_total": -1}},
        {"$project": {
            "_id": 0,
            "style": "$_id",
            "suggestion_count": 1,
            "average_total": {"$round": ["$average_total", 2]},
            "average_rating": {"$round": ["$average_rating", 1]},
            "highest_total": 1
        }}
    ]
    return make_response(jsonify(list(globals.designs.aggregate(pipeline))), 200)


# GET top products - the products most often included in suggestions
@reports_bp.route("/api/v1.0/reports/top-products", methods=["GET"])
@jwt_required
@admin_required
def report_top_products(current_user):
    try:
        limit = int(request.args.get("limit", 10))
        if limit < 1 or limit > 50:
            return make_response(jsonify({"error": "limit must be between 1 and 50"}), 400)
    except ValueError:
        return make_response(jsonify({"error": "limit must be a whole number"}), 400)

    pipeline = [
        {"$unwind": "$suggestions"},
        {"$unwind": "$suggestions.items"},
        {"$group": {
            "_id": "$suggestions.items.product_id",
            "name": {"$first": "$suggestions.items.name"},
            "category": {"$first": "$suggestions.items.category"},
            "times_suggested": {"$sum": 1}
        }},
        {"$sort": {"times_suggested": -1}},
        {"$limit": limit},
        {"$project": {
            "_id": 0,
            "product_id": "$_id",
            "name": 1,
            "category": 1,
            "times_suggested": 1
        }}
    ]
    return make_response(jsonify(list(globals.designs.aggregate(pipeline))), 200)
