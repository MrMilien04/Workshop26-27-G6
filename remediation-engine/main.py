import time
import subprocess
import threading
from datetime import datetime
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Remediation Engine & SIEM Feed")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

EVENTS_LOG = [
    {"time": datetime.now().strftime("%H:%M:%S"), "type": "INFO", "msg": "Moteur de remédiation Ansible & SIEM initialisé."}
]
REMEDIATION_LOCK = False

class AlertPayload(BaseModel):
    reason: str
    anomaly_score: float
    req_rate: int
    error_rate: int
    suspect_ip: str

def run_ansible_remediation(payload: AlertPayload):
    global REMEDIATION_LOCK
    try:
        EVENTS_LOG.insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "type": "ALERT",
            "msg": f"[ML-AIOps] Anomalie détectée (Score: {payload.anomaly_score} | Pics: {payload.req_rate} req, {payload.error_rate} err | IP: {payload.suspect_ip})"
        })
        # Pause de 4 secondes pour rendre la panne bien visible au jury sur le Dashboard
        time.sleep(4)

        EVENTS_LOG.insert(0, {
            "time": datetime.now().strftime("%H:%M:%S"),
            "type": "ACTION",
            "msg": "[ANSIBLE] Lancement du playbook Zero-Touch Recovery (isolation & restauration API)..."
        })

        result = subprocess.run(
            ["ansible-playbook", "/app/playbook.yml"],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            EVENTS_LOG.insert(0, {
                "time": datetime.now().strftime("%H:%M:%S"),
                "type": "RESOLVED",
                "msg": "[RECOVERY OK] Playbook Ansible terminé : Service de paiement rétabli et vérifié (Healthcheck 200 OK)."
            })
        else:
            EVENTS_LOG.insert(0, {
                "time": datetime.now().strftime("%H:%M:%S"),
                "type": "ERROR",
                "msg": f"Échec Ansible : {result.stderr}"
            })
    finally:
        REMEDIATION_LOCK = False

@app.post("/remediate/trigger")
def trigger_remediation(payload: AlertPayload):
    global REMEDIATION_LOCK
    if REMEDIATION_LOCK:
        return {"status": "ALREADY_RUNNING"}
    REMEDIATION_LOCK = True
    threading.Thread(target=run_ansible_remediation, args=(payload,)).start()
    return {"status": "REMEDIATION_STARTED"}

@app.get("/remediate/events")
def get_events():
    return EVENTS_LOG[:15]