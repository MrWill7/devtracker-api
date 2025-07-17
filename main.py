from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
import uuid
import os
import json

app = FastAPI()

USERS_FILE = "paid_users.json"
USAGE_LOG_FILE = "usage_log.json"
GUMROAD_PRODUCT_ID = "ctasfz"  # Change to your Gumroad product ID

# CORS (optional if you allow frontend requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this in production!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 🔄 Utility functions
def load_keys():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_keys(keys):
    with open(USERS_FILE, "w") as f:
        json.dump(keys, f, indent=2)

def log_usage(api_key: str, path: str):
    entry = {
        "api_key": api_key,
        "event_id": str(uuid.uuid4()),
        "path": path,
    }
    if os.path.exists(USAGE_LOG_FILE):
        with open(USAGE_LOG_FILE, "r") as f:
            usage = json.load(f)
    else:
        usage = []
    usage.append(entry)
    with open(USAGE_LOG_FILE, "w") as f:
        json.dump(usage, f, indent=2)


# 🔐 Global middleware for API key enforcement
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    # Allow webhook and root path without authentication
    if request.url.path in ["/", "/gumroad-webhook"]:
        return await call_next(request)

    x_api_key = request.headers.get("x-api-key")
    if not x_api_key:
        raise HTTPException(status_code=403, detail="Missing API key")

    keys = load_keys()

    if x_api_key not in keys:
        raise HTTPException(status_code=403, detail="Invalid API key")

    user_data = keys[x_api_key]
    if not user_data.get("active", False):
        raise HTTPException(status_code=403, detail="Inactive API key")

    if user_data["used"] >= user_data["quota"]:
        raise HTTPException(status_code=429, detail="Quota exceeded")

    # ⬆️ Increment usage
    user_data["used"] += 1
    save_keys(keys)

    # 🪵 Log usage
    log_usage(x_api_key, request.url.path)

    # Add user info into request state (optional)
    request.state.api_key = x_api_key
    request.state.user_data = user_data

    return await call_next(request)


# 🪝 Gumroad Webhook Endpoint
@app.post("/gumroad-webhook")
async def gumroad_webhook(request: Request):
    form_data = await request.form()

    if form_data.get("product_id") != GUMROAD_PRODUCT_ID:
        raise HTTPException(status_code=400, detail="Invalid product ID")

    new_key = str(uuid.uuid4())[:8]
    new_secret = str(uuid.uuid4())[:12]

    keys = load_keys()
    keys[new_key] = {
        "secret": new_secret,
        "active": True,
        "plan": "basic",
        "quota": 1000,
        "used": 0
    }
    save_keys(keys)

    return {
        "message": "✅ API key generated and stored",
        "api_key": new_key,
        "secret": new_secret
    }


# 🏠 Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to the DevTracker API 🚀"}


# 📊 Usage Tracking Endpoint
@app.post("/track")
async def track_usage(request: Request):
    try:
        body = await request.json()
        print(f"📦 Request body: {body}")
    except Exception as e:
        print(f"❗ JSON parse error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    return {
        "message": "Usage tracked successfully",
        "used": request.state.user_data["used"],
        "remaining": request.state.user_data["quota"] - request.state.user_data["used"],
    }
