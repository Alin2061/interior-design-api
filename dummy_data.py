import random
import json
import bcrypt
from datetime import datetime, timedelta

random.seed(42)

STYLES = ["modern", "minimalist", "scandinavian", "industrial",
          "bohemian", "mid-century", "traditional", "coastal"]

ROOM_TYPES = ["bedroom", "living room", "office", "kitchen"]

ROOM_OBJECTS = {
    "bedroom": ["double bed", "single bed", "wardrobe", "bedside table",
                "chest of drawers", "mirror", "rug"],
    "living room": ["sofa", "armchair", "coffee table", "tv unit",
                    "bookshelf", "floor lamp", "rug"],
    "office": ["desk", "office chair", "bookshelf", "filing cabinet",
               "desk lamp", "plant"],
    "kitchen": ["dining table", "dining chair", "bar stool",
                "kitchen island", "pendant light", "shelving"]
}


USER_IDS = ["USR-" + str(i) for i in range(1, 41)]

PRODUCT_ITEMS = {
    "furniture": ["bedside table", "wardrobe", "sofa", "armchair",
                  "coffee table", "desk", "office chair", "bookshelf",
                  "dining table", "dining chair", "bar stool", "tv unit",
                  "chest of drawers"],
    "decor": ["area rug", "wall mirror", "cushion set", "wall art",
              "plant pot", "throw blanket", "curtains", "vase"],
    "lighting": ["floor lamp", "table lamp", "pendant light",
                 "desk lamp", "wall light"],
    "paint": ["wall paint 2.5L", "wall paint 5L"]
}

MATERIALS = ["oak", "walnut", "pine", "metal", "rattan",
             "velvet", "linen", "marble", "glass", "wool"]

PAINT_FINISHES = ["matt", "silk", "eggshell"]

COLOURS = [
    {"name": "white", "hex": "#FFFFFF"},
    {"name": "warm grey", "hex": "#A8A39D"},
    {"name": "sage green", "hex": "#8DA399"},
    {"name": "navy", "hex": "#1F2A44"},
    {"name": "terracotta", "hex": "#C8664A"},
    {"name": "mustard", "hex": "#D4A531"},
    {"name": "black", "hex": "#1A1A1A"},
    {"name": "natural", "hex": "#D9C7A7"}
]

PRICE_RANGES = {
    "furniture": (60, 600),
    "decor": (15, 150),
    "lighting": (25, 200),
    "paint": (20, 60)
}

SIZE_RANGES = {
    "furniture": (40, 220),
    "decor": (10, 200),
    "lighting": (15, 180),
    "paint": (15, 25)
}

RETAILERS = [
    {"name": "HomeNest", "website": "https://homenest.example.com",
     "city": "Belfast", "coordinates": [-5.9301, 54.5973],
     "delivery_cost": 4.99, "delivery_days": 3},
    {"name": "Urban Living", "website": "https://urbanliving.example.com",
     "city": "London", "coordinates": [-0.1276, 51.5072],
     "delivery_cost": 6.99, "delivery_days": 2},
    {"name": "Nordic Rooms", "website": "https://nordicrooms.example.com",
     "city": "Manchester", "coordinates": [-2.2426, 53.4808],
     "delivery_cost": 0.0, "delivery_days": 5},
    {"name": "The Lamp House", "website": "https://lamphouse.example.com",
     "city": "Birmingham", "coordinates": [-1.8904, 52.4862],
     "delivery_cost": 3.50, "delivery_days": 4},
    {"name": "Paint Pot", "website": "https://paintpot.example.com",
     "city": "Glasgow", "coordinates": [-4.2518, 55.8642],
     "delivery_cost": 2.99, "delivery_days": 2},
    {"name": "Oak and Co", "website": "https://oakandco.example.com",
     "city": "Leeds", "coordinates": [-1.5491, 53.8008],
     "delivery_cost": 8.99, "delivery_days": 6}
]

REVIEW_COMMENTS = ["Great quality for the price", "Arrived damaged",
                   "Looks exactly like the picture", "Smaller than expected",
                   "Easy to assemble", "Colour is lovely",
                   "Would buy again", "Not worth the money",
                   "Fast delivery", "Feels very sturdy"]

START_DATE = datetime(2025, 11, 1)
END_DATE = datetime(2026, 10, 15)

STYLE_INFO = {
    "modern": {
        "description": "Clean lines, neutral colours and smooth surfaces.",
        "key_features": ["clean lines", "open space", "statement lighting"],
        "materials": ["metal", "glass", "marble"],
        "colours": ["white", "black", "warm grey"]
    },
    "minimalist": {
        "description": "Only what is needed, with calm and clutter-free rooms.",
        "key_features": ["hidden storage", "few accessories", "simple shapes"],
        "materials": ["oak", "linen", "glass"],
        "colours": ["white", "natural", "warm grey"]
    },
    "scandinavian": {
        "description": "Light woods, soft textiles and plenty of daylight.",
        "key_features": ["light wood", "cosy textiles", "plants"],
        "materials": ["pine", "oak", "wool"],
        "colours": ["white", "natural", "sage green"]
    },
    "industrial": {
        "description": "Raw materials inspired by warehouses and factories.",
        "key_features": ["exposed metal", "dark tones", "open shelving"],
        "materials": ["metal", "walnut", "glass"],
        "colours": ["black", "warm grey", "terracotta"]
    },
    "bohemian": {
        "description": "Relaxed and colourful, with layered patterns.",
        "key_features": ["patterned rugs", "lots of plants", "mixed textures"],
        "materials": ["rattan", "wool", "linen"],
        "colours": ["terracotta", "mustard", "sage green"]
    },
    "mid-century": {
        "description": "Retro 1950s shapes with tapered legs and warm wood.",
        "key_features": ["tapered legs", "organic curves", "bold accents"],
        "materials": ["walnut", "velvet", "metal"],
        "colours": ["mustard", "navy", "natural"]
    },
    "traditional": {
        "description": "Classic furniture, rich colours and symmetry.",
        "key_features": ["symmetry", "detailed woodwork", "rich fabrics"],
        "materials": ["walnut", "velvet", "marble"],
        "colours": ["navy", "natural", "terracotta"]
    },
    "coastal": {
        "description": "Bright and airy rooms inspired by the seaside.",
        "key_features": ["natural light", "woven textures", "soft blues"],
        "materials": ["rattan", "linen", "pine"],
        "colours": ["white", "navy", "natural"]
    }
}

FIRST_NAMES = ["Aoife", "Ciaran", "Priya", "James", "Sofia", "Liam",
               "Fatima", "Oliver", "Chloe", "Daniel", "Grace", "Arjun"]

LAST_NAMES = ["Murphy", "Smith", "Patel", "Kelly", "Brown", "Khan",
              "Wilson", "Byrne", "Taylor", "Walsh"]

CITIES = [
    {"city": "Belfast", "postcode_prefix": "BT"},
    {"city": "London", "postcode_prefix": "SW"},
    {"city": "Manchester", "postcode_prefix": "M"},
    {"city": "Birmingham", "postcode_prefix": "B"},
    {"city": "Glasgow", "postcode_prefix": "G"},
    {"city": "Leeds", "postcode_prefix": "LS"}
]

BUDGETS = [300, 500, 800, 1000, 1500, 2000]

OBJECT_CONDITIONS = ["good", "good", "worn", "damaged"]

LIGHT_LEVELS = ["low", "medium", "high"]

LIGHT_SOURCES = ["ceiling light", "floor lamp", "desk lamp",
                 "pendant light", "wall light", "spotlights"]

COLOUR_TEMPERATURES = [2700, 3000, 4000, 5000]

RESOLUTIONS = [
    {"width": 3024, "height": 4032},
    {"width": 4032, "height": 3024},
    {"width": 1920, "height": 1080},
    {"width": 1080, "height": 1920}
]

FEEDBACK_COMMENTS = ["Love the colours", "Too expensive", "Not my taste",
                     "Perfect for my room", "Great use of space",
                     "Would like more storage"]

COLOUR_HEX = {colour["name"]: colour["hex"] for colour in COLOURS}

DESIGN_STATUSES = ["completed"] * 17 + ["analysing"] * 2 + ["failed"]

ROOM_SIZES = {
    "bedroom": (2.5, 5.0),
    "living room": (3.5, 7.0),
    "office": (2.0, 4.0),
    "kitchen": (2.5, 5.5)
}

ROOM_NOTES = ["Needs more storage", "Very dark in the evenings",
              "Want it to feel bigger", "Keep the existing bed",
              "Pet friendly please", "Rented flat, no drilling",
              "Working from home here", ""]


def random_datetime(start=START_DATE, end=END_DATE):
    seconds = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, seconds))


def format_date(date):
    return date.strftime("%Y-%m-%dT%H:%M:%SZ")


def random_date(start=START_DATE, end=END_DATE):
    return format_date(random_datetime(start, end))


def generate_products(user_ids):
    product_list = []

    for i in range(1, 151):
        category = random.choice(list(PRODUCT_ITEMS.keys()))
        item = random.choice(PRODUCT_ITEMS[category])

        if category == "paint":
            colour = random.choice(COLOURS)
            name = colour["name"].title() + " " + item
        else:
            material = random.choice(MATERIALS)
            name = material.title() + " " + item

        low, high = PRICE_RANGES[category]
        base_price = random.uniform(low, high)

        variants = []
        for v in range(1, random.randint(1, 3) + 1):
            if category == "paint":
                variant_colour = colour
                variant_material = random.choice(PAINT_FINISHES)
            else:
                variant_colour = random.choice(COLOURS)
                variant_material = material

            variants.append({
                "variant_id": "VAR-" + str(i) + "-" + str(v),
                "colour": variant_colour["name"],
                "hex": variant_colour["hex"],
                "material": variant_material,
                "price": {
                    "amount": round(base_price * random.uniform(0.9, 1.2), 2),
                    "currency": "GBP"
                },
                "stock": random.randint(0, 50)
            })

        size_low, size_high = SIZE_RANGES[category]
        retailer = random.choice(RETAILERS)

        reviews = []
        reviewers = random.sample(user_ids, random.randint(0, 5))
        for r, reviewer in enumerate(reviewers, start=1):
            reviews.append({
                "review_id": "REV-" + str(i) + "-" + str(r),
                "user_id": reviewer,
                "score": random.randint(1, 5),
                "comment": random.choice(REVIEW_COMMENTS),
                "date": random_date()
            })

        if len(reviews) > 0:
            average = round(sum(rev["score"] for rev in reviews) / len(reviews), 1)
        else:
            average = 0

        product_list.append({
            "product_id": "PRD-" + str(i),
            "name": name,
            "category": category,
            "styles": random.sample(STYLES, random.randint(1, 3)),
            "dimensions": {
                "length": random.randint(size_low, size_high),
                "width": random.randint(size_low, size_high),
                "height": random.randint(size_low, size_high),
                "unit": "cm"
            },
            "variants": variants,
            "retailer": {
                "name": retailer["name"],
                "website": retailer["website"],
                "city": retailer["city"],
                "location": {
                    "type": "Point",
                    "coordinates": retailer["coordinates"]
                },
                "delivery": {
                    "cost": retailer["delivery_cost"],
                    "days": retailer["delivery_days"]
                }
            },
            "ratings": {
                "average": average,
                "count": len(reviews),
                "reviews": reviews
            }
        })

    return product_list


def generate_styles():
    style_list = []

    for i, name in enumerate(STYLES, start=1):
        info = STYLE_INFO[name]
        palette = [colour for colour in COLOURS if colour["name"] in info["colours"]]

        style_list.append({
            "style_id": "STY-" + str(i),
            "name": name,
            "description": info["description"],
            "key_features": info["key_features"],
            "materials": info["materials"],
            "colour_palette": palette,
            "created_at": random_date(START_DATE, datetime(2025, 12, 1))
        })

    return style_list


def generate_users(user_ids):
    user_list = []

    for i, user_id in enumerate(user_ids, start=1):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        username = first.lower() + str(i)
        location = random.choice(CITIES)

        if i <= 2:
            role = "admin"
            password = "admin123"
        else:
            role = "user"
            password = "password123"

        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        postcode = (location["postcode_prefix"] + str(random.randint(1, 20)) + " "
                    + str(random.randint(1, 9))
                    + random.choice("ABDEFGHJLNPQRSTUWXYZ")
                    + random.choice("ABDEFGHJLNPQRSTUWXYZ"))

        user_list.append({
            "user_id": user_id,
            "username": username,
            "password": hashed.decode("utf-8"),
            "profile": {
                "name": first + " " + last,
                "email": username + "@example.com",
                "address": {
                    "city": location["city"],
                    "postcode": postcode,
                    "country": "United Kingdom"
                }
            },
            "account": {
                "role": role,
                "created_at": random_date(START_DATE, datetime(2026, 6, 1)),
                "last_login": random_date(datetime(2026, 6, 1), END_DATE)
            },
            "saved_preferences": {
                "favourite_styles": random.sample(STYLES, random.randint(1, 3)),
                "default_budget": {
                    "amount": random.choice(BUDGETS),
                    "currency": "GBP"
                }
            },
            "saved_designs": []
        })

    return user_list


def generate_analysis(room_type, resolution):
    detected_objects = []
    labels = random.sample(ROOM_OBJECTS[room_type], random.randint(2, 4))

    for label in labels:
        box_width = random.randint(300, resolution["width"] // 2)
        box_height = random.randint(300, resolution["height"] // 2)

        detected_objects.append({
            "label": label,
            "confidence": round(random.uniform(0.6, 0.99), 2),
            "condition": random.choice(OBJECT_CONDITIONS),
            "bounding_box": {
                "x": random.randint(0, resolution["width"] - box_width),
                "y": random.randint(0, resolution["height"] - box_height),
                "width": box_width,
                "height": box_height
            }
        })

    main_colours = random.sample(COLOURS, 3)
    first = random.randint(40, 60)
    second = random.randint(15, 100 - first - 10)
    third = 100 - first - second

    colour_palette = []
    for colour, percentage in zip(main_colours, [first, second, third]):
        colour_palette.append({
            "hex": colour["hex"],
            "name": colour["name"],
            "percentage": percentage
        })

    window_count = random.randint(0, 3)
    if window_count == 0:
        natural_light = "low"
    else:
        natural_light = random.choice(LIGHT_LEVELS)

    sources = []
    for source in random.sample(LIGHT_SOURCES, random.randint(1, 2)):
        sources.append({
            "type": source,
            "colour_temperature_k": random.choice(COLOUR_TEMPERATURES)
        })

    return {
        "model": {
            "name": "RoomVision",
            "version": "2.1",
            "processing_time_ms": random.randint(900, 2500)
        },
        "detected_objects": detected_objects,
        "colour_palette": colour_palette,
        "lighting": {
            "natural_light": natural_light,
            "window_count": window_count,
            "sources": sources
        }
    }


def generate_suggestion(design_number, suggestion_number, style, budget,
                        products, resolution, completed_at):
    if budget["is_flexible"]:
        limit = budget["amount"] * 1.1
    else:
        limit = budget["amount"]

    matching = [product for product in products if style in product["styles"]]
    random.shuffle(matching)

    items = []
    costs = {"furniture": 0, "decor": 0, "lighting": 0, "paint": 0}
    total = 0
    has_paint = False

    for product in matching:
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
            "price": {
                "amount": price,
                "currency": "GBP"
            },
            "placement": {
                "x": random.randint(0, resolution["width"]),
                "y": random.randint(0, resolution["height"]),
                "rotation": random.choice([0, 90, 180, 270])
            }
        })

        costs[product["category"]] += price
        total += price

    colour_scheme = []
    for area, colour_name in zip(["walls", "floor", "accent"], STYLE_INFO[style]["colours"]):
        colour_scheme.append({
            "area": area,
            "name": colour_name,
            "hex": COLOUR_HEX[colour_name]
        })

    if random.random() < 0.7:
        rating = random.randint(1, 5)
        comment = random.choice(FEEDBACK_COMMENTS)
        is_favourite = rating >= 4 and random.random() < 0.6
    else:
        rating = None
        comment = ""
        is_favourite = False

    generated_at = completed_at - timedelta(seconds=random.randint(1, 20))

    return {
        "suggestion_id": "SUG-" + str(suggestion_number),
        "style": style,
        "preview_image": {
            "url": "https://storage.example.com/previews/dsn-" + str(design_number)
                   + "-sug-" + str(suggestion_number) + ".png",
            "generated_at": format_date(generated_at)
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
        "feedback": {
            "rating": rating,
            "comment": comment,
            "is_favourite": is_favourite
        }
    }

def generate_designs(users, products):
    design_list = []
    normal_users = [user for user in users if user["account"]["role"] == "user"]

    for i in range(1, 301):
        user = random.choice(normal_users)
        room_type = random.choice(ROOM_TYPES)
        resolution = random.choice(RESOLUTIONS)
        status = random.choice(DESIGN_STATUSES)

        size_low, size_high = ROOM_SIZES[room_type]
        styles_wanted = random.sample(STYLES, random.randint(1, 2))
        budget = {
            "amount": random.choice(BUDGETS),
            "currency": "GBP",
            "is_flexible": random.random() < 0.3
        }

        uploaded_at = random_datetime(datetime(2026, 1, 1), END_DATE)
        analysing_at = uploaded_at + timedelta(seconds=random.randint(1, 5))
        finished_at = analysing_at + timedelta(seconds=random.randint(20, 90))

        status_history = [
            {"status": "uploaded", "at": format_date(uploaded_at)},
            {"status": "analysing", "at": format_date(analysing_at)}
        ]

        analysis = None
        suggestions = []

        if status == "completed":
            analysis = generate_analysis(room_type, resolution)
            for s in range(1, random.randint(1, 3) + 1):
                style = random.choice(styles_wanted)
                suggestions.append(generate_suggestion(i, s, style, budget, products,
                                                       resolution, finished_at))
            status_history.append({"status": "completed", "at": format_date(finished_at)})
            updated_at = finished_at
        elif status == "failed":
            status_history.append({"status": "failed", "at": format_date(finished_at)})
            updated_at = finished_at
        else:
            updated_at = analysing_at

        design_list.append({
            "design_id": "DSN-" + str(i),
            "user_id": user["user_id"],
            "title": room_type.title() + " makeover " + str(i),
            "room": {
                "type": room_type,
                "dimensions": {
                    "length": round(random.uniform(size_low, size_high), 1),
                    "width": round(random.uniform(size_low, size_high), 1),
                    "unit": "m"
                },
                "notes": random.choice(ROOM_NOTES)
            },
            "original_image": {
                "url": "https://storage.example.com/uploads/dsn-" + str(i) + ".jpg",
                "format": "jpg",
                "resolution": resolution,
                "size_kb": random.randint(800, 4500),
                "uploaded_at": format_date(uploaded_at)
            },
            "preferences": {
                "styles": styles_wanted,
                "budget": budget
            },
            "status": status,
            "status_history": status_history,
            "analysis": analysis,
            "suggestions": suggestions,
            "created_at": format_date(uploaded_at),
            "updated_at": format_date(updated_at)
        })

    return design_list


def link_saved_designs(users, designs):
    for user in users:
        for design in designs:
            if design["user_id"] != user["user_id"]:
                continue
            for suggestion in design["suggestions"]:
                if suggestion["feedback"]["is_favourite"]:
                    user["saved_designs"].append(design["design_id"])
                    break



def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as fout:
        json.dump(data, fout, indent=4)
    print("Saved", len(data), "documents to", filename)


products = generate_products(USER_IDS)
styles = generate_styles()
users = generate_users(USER_IDS)
designs = generate_designs(users, products)
link_saved_designs(users, designs)

save_json("products.json", products)
save_json("styles.json", styles)
save_json("users.json", users)
save_json("designs.json", designs)