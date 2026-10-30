from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
db = client.interiorDB

designs = db.designs
users = db.users
products = db.products
styles = db.styles
blacklist = db.blacklist

secret_key = "com661-interior-design-api-secret-key-2026"

ROOM_TYPES = ["bedroom", "living room", "office", "kitchen"]
CATEGORIES = ["furniture", "decor", "lighting", "paint"]
