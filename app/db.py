from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import MongoClient
from . import config

client = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=5000)
client.admin.command("ping")  # fail loudly at startup if Mongo is unreachable
conversations = client[config.MONGODB_DB]["conversations"]


def now():
    return datetime.now(timezone.utc)


def to_oid(id_str):
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError):
        return None


def serialize(doc, with_messages=True):
    out = {"id": str(doc["_id"]), "title": doc["title"], "updated_at": doc["updated_at"].isoformat()}
    if with_messages:
        out["messages"] = [{**m, "created_at": m["created_at"].isoformat()} for m in doc["messages"]]
    return out