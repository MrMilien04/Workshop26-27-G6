# Documentation Officielle & Procédures SecOps - PROJECT RESILIENCE-ALPHA

## 1. Architecture & Flux du SI de Paiement
Le système de paiement est composé de microservices isolés sur le réseau interne Docker (`internal_net`) :
- WAF / Reverse Proxy (Nginx) : Point d'entrée unique sur le port 80, filtre les injections SQLi/XSS.
- Auth Service (FastAPI) : Délivre et vérifie les jetons JWT (HS256) avec HashiCorp Vault pour la gestion des secrets.
- Payment API (FastAPI) : Traite les transactions marchandes et stocke les opérations dans PostgreSQL 15.
- Moteur ML AIOps : Utilise l'algorithme Isolation Forest (scikit-learn) sur une fenêtre glissante de 3 secondes (taux de requêtes et taux d'erreurs HTTP 5xx).

## 2. Procédure de Réponse à Incident (Zero-Touch Recovery)
Lorsqu'une anomalie est détectée (score Isolation Forest négatif ou dégradation de service HTTP 503) :
1. Le service `ml-detector` transmet immédiatement une alerte JSON au moteur `remediation-engine`.
2. Le moteur journalise l'incident dans le SIEM et déclenche le playbook Ansible `playbook.yml`.
3. Le playbook Ansible purge l'état dégradé de l'API (`/api/chaos/restore`) et exécute un test de santé (`/api/health`).
4. L'opérateur doit vérifier qu'une nouvelle transaction fictive passe avec le statut `COMPLETED`.
Attention : Conformément à la politique de sécurité, l'assistant RAG n'a aucun droit d'exécution sur les conteneurs (séparation stricte entre l'aide à la décision et l'automate de remédiation).

## 3. Objectifs PCA / PRA et Conformité NIS2 / DORA
- RTO (Recovery Time Objective - Durée maximale d'interruption admissible) : 15 secondes grâce à l'automatisation Ansible (mesuré à 5 secondes lors des tests).
- RPO (Recovery Point Objective - Perte de données maximale admissible) : 0 transaction perdue (transactions atomiques ACID sous PostgreSQL avec volume persistant `db_data`).
- Conformité DORA (Digital Operational Resilience Act) : Surveillance continue des services financiers critiques, tests de résilience par Chaos Engineering et journalisation centralisée (Loki/Prometheus).
- Conformité NIS2 : Gestion des incidents, sécurisation de la chaîne d'approvisionnement logicielle, contrôle d'accès par jetons JWT et gestion des secrets via HashiCorp Vault.