import time
import requests
import concurrent.futures

# Remplacez par 192.168.137.1 depuis le PC Attaquant (ou localhost en test local)
TARGET = "http://localhost"

print("==========================================================")
print(" [RED TEAM] LANCEMENT DU SCÉNARIO D'ATTAQUE SUR LE SI")
print("==========================================================")

# 1. Tentatives d'injection SQL (filtrées par le WAF Nginx -> code 403 dans Loki)
print("[1/3] Envoi de payloads SQLi sur le WAF...")
for i in range(5):
    r = requests.get(f"{TARGET}/api/transactions?id=1%20UNION%20SELECT%20username,password%20FROM%20users")
    print(f"  -> Payload SQLi #{i+1} : Code HTTP {r.status_code} (Attendu: 403 WAF Block)")

# 2. Déclenchement de l'incident & Flood intensif pour faire bondir Prometheus/Grafana
print("\n[2/3] Saturation de l'API Métier & Déclenchement de l'anomalie critique...")

def send_flood(i):
    try:
        if i % 2 == 0:
            return requests.post(f"{TARGET}/api/chaos/trigger", timeout=2).status_code
        else:
            return requests.get(f"{TARGET}/api/health", timeout=2).status_code
    except Exception:
        return 503

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(send_flood, range(40)))

print(f"  -> 40 requêtes offensives envoyées ! Codes HTTP reçus : {set(results)}")
print("\n[3/3] Attaque terminée. Observez la détection ML et la remédiation Ansible sur le Dashboard !")