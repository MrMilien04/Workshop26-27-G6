import os
import time
import jwt
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Auth Service")
JWT_SECRET = os.getenv("JWT_SECRET", "secret")

class LoginRequest(BaseModel):
    username: str
    password: str

USERS = {
    "merchant_alpha": "pass_alpha_2026",
    "operator": "admin_resilience"
}

@app.post("/auth/token")
def login(req: LoginRequest):
    if USERS.get(req.username) != req.password:
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    payload = {
        "sub": req.username,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer"}

@app.get("/auth/verify")
def verify(token: str):
    try:
        decoded = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return {"valid": True, "user": decoded["sub"]}
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")