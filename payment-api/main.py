import os
import time
import psycopg2
import requests
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

app = FastAPI(title="Payment API")
Instrumentator().instrument(app).expose(app)

DB_URL = os.getenv("DATABASE_URL")
AUTH_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-service:8000")

# État interne pour le Chaos Engineering et télémétrie ML
SERVICE_STATE = {
    "degraded": False,
    "req_count_window": 0,
    "error_count_window": 0,
    "last_suspect_ip": "none"
}

def get_db():
    return psycopg2.connect(DB_URL)

@app.on_event("startup")
def init_db():
    for _ in range(10):
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id SERIAL PRIMARY KEY,
                    merchant VARCHAR(50),
                    amount NUMERIC(10, 2),
                    currency VARCHAR(10),
                    status VARCHAR(20),
                    client_ip VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            cur.close()
            conn.close()
            break
        except Exception:
            time.sleep(2)

class PaymentRequest(BaseModel):
    amount: float
    currency: str = "EUR"

@app.middleware("http")
async def track_metrics(request: Request, call_next):
    SERVICE_STATE["req_count_window"] += 1
    client_ip = request.headers.get("X-Real-IP", request.client.host)
    response = await call_next(request)
    if response.status_code >= 500:
        SERVICE_STATE["error_count_window"] += 1
        SERVICE_STATE["last_suspect_ip"] = client_ip
    return response

@app.get("/api/health")
def health_check():
    if SERVICE_STATE["degraded"]:
        raise HTTPException(status_code=503, detail="Service dégradé suite à une anomalie critique")
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        cur.close()
        conn.close()
        return {"status": "HEALTHY", "db": "CONNECTED"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")

@app.get("/api/telemetry")
def get_telemetry():
    """Point de collecte pour le modèle ML Isolation Forest"""
    data = {
        "req_rate": SERVICE_STATE["req_count_window"],
        "error_rate": SERVICE_STATE["error_count_window"],
        "degraded": 1 if SERVICE_STATE["degraded"] else 0,
        "suspect_ip": SERVICE_STATE["last_suspect_ip"]
    }
    # Réinitialisation de la fenêtre glissante après lecture
    SERVICE_STATE["req_count_window"] = 0
    SERVICE_STATE["error_count_window"] = 0
    return data

@app.post("/api/chaos/trigger")
def trigger_incident(request: Request):
    """Simule un incident de sécurité / dégradation critique depuis un poste distant"""
    client_ip = request.headers.get("X-Real-IP", request.client.host)
    SERVICE_STATE["degraded"] = True
    SERVICE_STATE["req_count_window"] += 150
    SERVICE_STATE["error_count_window"] += 95
    SERVICE_STATE["last_suspect_ip"] = client_ip
    raise HTTPException(status_code=500, detail="Anomalie critique générée")

@app.post("/api/chaos/restore")
def restore_service():
    """Action corrective appelée uniquement par le playbook Ansible de remédiation"""
    SERVICE_STATE["degraded"] = False
    SERVICE_STATE["req_count_window"] = 0
    SERVICE_STATE["error_count_window"] = 0
    return {"status": "RESTORED"}

@app.post("/api/pay")
def process_payment(req: PaymentRequest, request: Request, authorization: str = Header(None)):
    if SERVICE_STATE["degraded"]:
        raise HTTPException(status_code=503, detail="Paiement refusé : SI en mode dégradé")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")
    
    token = authorization.split(" ")[1]
    auth_resp = requests.get(f"{AUTH_URL}/auth/verify", params={"token": token}, timeout=3)
    if auth_resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Non autorisé")
    
    merchant = auth_resp.json().get("user")
    client_ip = request.headers.get("X-Real-IP", request.client.host)

    if req.amount <= 0 or req.amount > 100000:
        raise HTTPException(status_code=400, detail="Montant invalide")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO transactions (merchant, amount, currency, status, client_ip) VALUES (%s, %s, %s, %s, %s) RETURNING id;",
        (merchant, req.amount, req.currency, "COMPLETED", client_ip)
    )
    tx_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    return {"transaction_id": tx_id, "status": "COMPLETED", "merchant": merchant, "amount": req.amount}

@app.get("/api/transactions")
def list_transactions():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, merchant, amount, currency, status, client_ip, created_at FROM transactions ORDER BY id DESC LIMIT 20;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {"id": r[0], "merchant": r[1], "amount": float(r[2]), "currency": r[3], "status": r[4], "ip": r[5], "timestamp": str(r[6])}
        for r in rows
    ]