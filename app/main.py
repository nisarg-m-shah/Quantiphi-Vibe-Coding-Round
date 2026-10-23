import json
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from . import db, llm

app = FastAPI()
Tone = Literal["professional", "casual", "concise"]


class ChatIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    tone: Tone


class RegenIn(BaseModel):
    tone: Tone


def get_conv(id):
    oid = db.to_oid(id)
    doc = db.conversations.find_one({"_id": oid}) if oid else None
    if not doc:
        raise HTTPException(404, "Conversation not found")
    return doc


def sse(payload):
    return f"data: {json.dumps(payload)}\n\n"


def run_stream(history, tone, on_complete):
    parts = []
    try:
        for tok in llm.stream_reply(history, tone):
            parts.append(tok)
            yield sse({"token": tok})
    except Exception as e:
        yield sse({"error": llm.friendly_error(e)})
        return
    full = "".join(parts)
    if not full.strip():
        yield sse({"error": "Empty response from model."})
        return
    on_complete(full)  # save only after the stream fully completes
    yield sse({"done": True})


def plain(msgs):
    return [{"role": m["role"], "content": m["content"]} for m in msgs]


@app.get("/api/conversations")
def list_convs():
    docs = db.conversations.find({}, {"title": 1, "updated_at": 1}).sort("updated_at", -1)
    return [db.serialize(d, False) for d in docs]


@app.post("/api/conversations")
def create_conv():
    t = db.now()
    r = db.conversations.insert_one({"title": "New chat", "created_at": t, "updated_at": t, "messages": []})
    return {"id": str(r.inserted_id)}


@app.get("/api/conversations/{id}")
def read_conv(id: str):
    return db.serialize(get_conv(id))


@app.post("/api/conversations/{id}/messages")
def send_message(id: str, body: ChatIn):
    conv = get_conv(id)
    content = body.content.strip()
    if not content:
        raise HTTPException(400, "Message is empty")
    history = plain(conv["messages"]) + [{"role": "user", "content": content}]

    def save(full):
        t = db.now()
        update = {
            "$push": {"messages": {"$each": [
                {"role": "user", "content": content, "tone": body.tone, "created_at": t},
                {"role": "assistant", "content": full, "tone": body.tone, "created_at": t},
            ]}},
            "$set": {"updated_at": t},
        }
        if not conv["messages"]:
            update["$set"]["title"] = content[:40]
        db.conversations.update_one({"_id": conv["_id"]}, update)

    return StreamingResponse(run_stream(history, body.tone, save), media_type="text/event-stream")


@app.post("/api/conversations/{id}/regenerate")
def regenerate(id: str, body: RegenIn):
    conv = get_conv(id)
    msgs = conv["messages"]
    if not msgs or msgs[-1]["role"] != "assistant":
        raise HTTPException(400, "Nothing to regenerate")
    idx = len(msgs) - 1
    history = plain(msgs[:-1])

    def save(full):
        t = db.now()
        new_msg = {"role": "assistant", "content": full, "tone": body.tone, "created_at": t}
        # Replace only the last answer, and only if nothing was added since.
        db.conversations.update_one(
            {"_id": conv["_id"], f"messages.{idx + 1}": {"$exists": False}},
            {"$set": {f"messages.{idx}": new_msg, "updated_at": t}},
        )

    return StreamingResponse(run_stream(history, body.tone, save), media_type="text/event-stream")


app.mount("/", StaticFiles(directory="static", html=True), name="static")  # keep last