import json
from pymongo import MongoClient, GEOSPHERE, TEXT

client = MongoClient("mongodb://localhost:27017")
db = client.interiorDB


def load_collection(name):
    with open(name + ".json", "r", encoding="utf-8") as fin:
        documents = json.load(fin)

    db[name].drop()
    db[name].insert_many(documents)
    print("Loaded", db[name].count_documents({}), "documents into", name)


for name in ["products", "styles", "users", "designs"]:
    load_collection(name)

db.products.create_index([("retailer.location", GEOSPHERE)])
db.products.create_index([("name", TEXT), ("category", TEXT)])
db.users.create_index("username", unique=True)
db.designs.create_index("user_id")
print("Indexes created")