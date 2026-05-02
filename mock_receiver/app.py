import asyncio
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel


Mode = Literal["success", "fail", "flaky", "timeout"]

app = FastAPI(title="Webhook Mock Receiver")
state = {"mode": "success", "attempts": 0}


class ModeRequest(BaseModel):
    mode: Mode


@app.get("/health")
async def health():
    return {"ok": True, "mode": state["mode"], "attempts": state["attempts"]}


@app.post("/mode")
async def set_mode(request: ModeRequest):
    state["mode"] = request.mode
    state["attempts"] = 0
    return {"mode": state["mode"], "attempts": state["attempts"]}


@app.post("/webhook")
async def webhook(request: Request):
    state["attempts"] += 1
    payload = await request.json()
    mode = state["mode"]

    if mode == "success":
        return {"received": True, "attempt": state["attempts"], "payload": payload}
    if mode == "fail":
        raise HTTPException(status_code=500, detail="Mock receiver forced failure")
    if mode == "flaky" and state["attempts"] <= 2:
        raise HTTPException(status_code=500, detail="Mock receiver flaky failure")
    if mode == "timeout":
        await asyncio.sleep(6)
        return {"received": True, "attempt": state["attempts"], "payload": payload}

    return {"received": True, "attempt": state["attempts"], "payload": payload}
