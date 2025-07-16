from fastapi import FastAPI, Request, Header, HTTPException
from datetime import datetime
import json
import os
import uuid

app = FastAPI()

DATA_FILE = "usage_db.json"
USERS_FILE = "paid_users.json"

# Load usage data
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        usage_data = json.load(f)
else:
    usage_data = {}

# Load user database
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f:
        VALID_KEYS = json.load(f)
else:
    VALID_KEYS = {}

@app.post("/register")
async def register():
    new_key = str(uuid.uuid4())[:8]
    new_secret = str(uuid.uuid4())[:12]

    VALID_KEYS[new_key] = {
        "secret": new_secret,
        "active": True,
        "plan": "basic",
        "quota": 1000,
        "used": 0
    }

    with open(USERS_FILE, "w") as f:
        json.dump(VALID_KEYS, f, indent=2)

    return {
        "message": "API key created!",
        "api_key": new_key,
        "secret": new_secret,
        "plan": "basic"
    }

@app.post("/register/premium")
async def register_premium():
    new_key = str(uuid.uuid4())[:8]
    new_secret = str(uuid.uuid4())[:12]

    VALID_KEYS[new_key] = {
        "secret": new_secret,
        "active": True,
        "plan": "premium",
        "quota": 10000,
        "used": 0
    }

    with open(USERS_FILE, "w") as f:
        json.dump(VALID_KEYS, f, indent=2)

    return {
        "message": "Premium API key created!",
        "api_key": new_key,
        "secret": new_secret,
        "plan": "premium"
    }

@app.post("/track")
async def track_usage(request: Request):
    body = await request.json()
    api_key = body.get("api_key")
    status = body.get("status", 200)
    timestamp = datetime.utcnow().isoformat()

    if api_key not in VALID_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")

    user = VALID_KEYS[api_key]
    if not user["active"]:
        raise HTTPException(status_code=403, detail="Account inactive")

    if user["used"] >= user["quota"]:
        raise HTTPException(status_code=403, detail="Quota exceeded")

    if api_key not in usage_data:
        usage_data[api_key] = []

    usage_data[api_key].append({
        "timestamp": timestamp,
        "status": status
    })

    # Update usage and save
    user["used"] += 1
    VALID_KEYS[api_key] = user

    with open(DATA_FILE, "w") as f:
        json.dump(usage_data, f, indent=2)
    with open(USERS_FILE, "w") as f:
        json.dump(VALID_KEYS, f, indent=2)

    return {"message": "Usage tracked."}

@app.get("/summary/{api_key}")
def get_summary(api_key: str, x_api_secret: str = Header(None)):
    if api_key not in VALID_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")

    user = VALID_KEYS[api_key]
    if user["secret"] != x_api_secret:
        raise HTTPException(status_code=401, detail="Invalid API secret")

    logs = usage_data.get(api_key, [])
    total = len(logs)
    errors = sum(1 for l in logs if l["status"] != 200)

    return {
        "api_key": api_key,
        "plan": user["plan"],
        "used": user["used"],
        "quota": user["quota"],
        "remaining": user["quota"] - user["used"],
        "total_requests": total,
        "errors": errors
    }
