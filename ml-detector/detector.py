import time
import requests
import numpy as np
from sklearn.ensemble import IsolationForest

PAYMENT_API_URL = "http://payment-api:8000"
REMEDIATION_URL = "http://remediation-engine:8000"

print("[ML-AIOps] Initialisation et entraînement du modèle Isolation Forest...")

# Jeu d'entraînement représentant le comportement nominal [req_rate, error_rate]
rng = np.random.RandomState(42)
normal_traffic = np.column_stack([
    rng.randint(1, 25, size=200),  # 1 à 25 requêtes par fenêtre de 3s
    rng.randint(0, 2, size=200)    # 0 à 1 erreur isolée tolérée
])

model = IsolationForest(n_estimators=100, contamination=0.02, random_state=42)
model.fit(normal_traffic)
print("[ML-AIOps] Modèle entraîné avec succès. Surveillance active...")

while True:
    try:
        resp = requests.get(f"{PAYMENT_API_URL}/api/telemetry", timeout=3)
        if resp.status_code == 200:
            telemetry = resp.json()
            features = np.array([[telemetry["req_rate"], telemetry["error_rate"]]])
            prediction = model.predict(features)[0]
            score = float(model.decision_function(features)[0])

            # -1 indique une anomalie détectée par Isolation Forest (ou état dégradé persistant)
            if prediction == -1 or telemetry["degraded"] == 1:
                print(f"[ALERTE ML] Anomalie détectée ! Features={features.tolist()}, Score={score:.3f}")
                requests.post(
                    f"{REMEDIATION_URL}/remediate/trigger",
                    json={
                        "reason": "IsolationForest Anomaly Detected",
                        "anomaly_score": round(score, 4),
                        "req_rate": telemetry["req_rate"],
                        "error_rate": telemetry["error_rate"],
                        "suspect_ip": telemetry["suspect_ip"]
                    },
                    timeout=5
                )
    except Exception as e:
        print(f"[ML-AIOps] Attente des services ({e})...")

    time.sleep(3)