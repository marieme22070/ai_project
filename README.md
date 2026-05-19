# N-ID — Plateforme IA d'annotation et de normalisation d'identité multilingue

**AI-powered long-context identity annotation system for multilingual African administrative data.**

Projet positionné pour **FlagOS Open Computing Global Challenge — Track 3 : Automatic Data Annotation in Long-Context Scenarios**.

Plateforme d'annotation intelligente, moteur d'analyse d'identité et traitement de documents administratifs longs pour la **République Islamique de Mauritanie** — arabe, français, hassaniya, pulaar, wolof.

---

## Table des matières

1. [Vue d'ensemble](#vue-densemble)
2. [Structure du projet](#structure-du-projet)
3. [Prérequis](#prérequis)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Lancer le projet](#lancer-le-projet)
7. [Vérification](#vérification)
8. [Dépannage](#dépannage)
9. [Innovation IA](#innovation-ia)
10. [Architecture](#architecture)
11. [API](#api)
12. [Compte administrateur](#compte-administrateur)
13. [Licence](#licence)

---

## Vue d'ensemble

N-ID combine un **backend FastAPI** (moteur d'annotation, identity graph, Whisper) et un **frontend React + Vite** (tableau de bord). En développement, le frontend proxy les requêtes API vers le backend sur le port **8000**.

| Composant | Technologie | Port par défaut |
|-----------|-------------|-----------------|
| Backend API | FastAPI + Uvicorn | `8000` |
| Frontend | React 18 + Vite 6 | `5173` |
| Base de données | SQLite (fichier local) | — |
| Elasticsearch | Optionnel (désactivé par défaut) | `9200` |

---

## Structure du projet

```
hack/
├── .env.example          # Configuration (lue par le backend à la racine)
├── venv/                 # Environnement Python recommandé (à la racine)
├── backend/
│   ├── main.py           # Point d'entrée FastAPI → module `main:app`
│   ├── run.ps1           # Script PowerShell de démarrage
│   ├── requirements.txt  # Dépendances Python (à utiliser)
│   ├── ARCHITECTURE.md   # Détail des 7 couches N-ID
│   ├── app/              # Code métier (API, pipeline, modèles)
│   └── data/             # SQLite et fichiers générés
└── frontend/
    ├── package.json
    └── vite.config.js    # Proxy vers http://127.0.0.1:8000
```

> **Important :** l'application ASGI n'est **pas** `app.main:app`. Le fichier `main.py` se trouve directement dans `backend/`, donc le module correct est **`main:app`**, et les commandes doivent être exécutées **depuis le dossier `backend/`**.

---

## Prérequis

| Outil | Version recommandée |
|-------|---------------------|
| **Python** | 3.11 ou 3.12 |
| **Node.js** | 18+ (LTS) |
| **npm** | fourni avec Node.js |
| **Git** | pour cloner le dépôt |

Optionnel :

- **FFmpeg** — pour le traitement audio avancé (`ffmpeg-python`, Whisper)
- **PostgreSQL** — si vous remplacez SQLite via `DATABASE_URL`
- **Elasticsearch 8.x** — si `ELASTICSEARCH_ENABLED=true`

---

## Installation

### 1. Cloner et ouvrir le projet

```powershell
cd C:\Users\PC\Desktop\hack
```

*(Adaptez le chemin selon votre machine.)*

### 2. Environnement virtuel Python (racine du projet)

Créez le venv **à la racine** `hack/`, pas dans `backend/` :

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Sous **cmd** :

```cmd
venv\Scripts\activate.bat
```

### 3. Dépendances backend

```powershell
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
```

> Utilisez **`backend\requirements.txt`**. Le fichier `requirements.txt` à la racine peut contenir des marqueurs de conflit Git ; en cas de doute, ne l'utilisez pas.

### 4. Dépendances frontend

```powershell
cd frontend
npm install
cd ..
```

---

## Configuration

Le backend charge **uniquement** le fichier **`hack/.env.example`** à la racine du dépôt (voir `backend/app/config.py`). Il n'est pas nécessaire de copier ce fichier vers `backend/`.

### OpenAI API — bloc copier-coller

1. Créez ou ouvrez le fichier **`hack/.env.example`** à la racine du projet.
2. **Copiez-collez** tout le bloc ci-dessous (remplacez le contenu existant si besoin).
3. **Enlevez le `#` (commentaire) devant `OPENAI_API_KEY`** — sinon la clé n'est pas lue par le backend.
4. Redémarrez le backend après modification.

#### Important : décommenter la clé OpenAI

Dans le dépôt, la ligne de la clé peut être **commentée** par sécurité :

```env
# ❌ Ne fonctionne pas (ligne ignorée)
# OPENAI_API_KEY=your_openai_api_key_here
```

**Supprimez uniquement le `#` au début de cette ligne** (gardez les `#` des autres lignes de commentaire explicatif) :

```env
# ✅ Correct — la clé est active
OPENAI_API_KEY=votre-cle-openai-ici
```

> Les lignes qui commencent par `#` sans nom de variable (ex. `# Application`, `# OpenAI`) restent des commentaires — **ne les supprimez pas**, elles n'empêchent pas le chargement de la config.

```env
# Application
DEBUG=false
SECRET_KEY=change-me-generate-with-openssl-rand-hex-32
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# OpenAI (obligatoire pour IA complete, sinon regles de repli)
OPENAI_API_KEY=votre-cle-openai-ici

# Modeles OpenAI (optionnel — valeurs par defaut du backend)
# OPENAI_MODEL_CORRECTION=gpt-4.1-mini
# OPENAI_MODEL_COMPLEX=gpt-4.1
# OPENAI_MODEL_WHISPER=whisper-1
# OPENAI_MODEL_EMBEDDING=text-embedding-3-large

# Base locale SQLite (aucun PostgreSQL requis)
DATABASE_URL=sqlite:///./data/mauritania_names.db

# Elasticsearch desactive par defaut
ELASTICSEARCH_ENABLED=false
ELASTICSEARCH_URL=http://localhost:9200

# Matching
FUZZY_THRESHOLD=75
EMBEDDING_SIMILARITY_THRESHOLD=0.85
```

| Variable | Rôle |
|----------|------|
| `OPENAI_API_KEY` | Clé API — GPT, embeddings, Whisper |
| `OPENAI_MODEL_CORRECTION` | Normalisation / cas simples (`gpt-4.1-mini`) |
| `OPENAI_MODEL_COMPLEX` | Documents longs / cas complexes (`gpt-4.1`) |
| `OPENAI_MODEL_WHISPER` | Transcription audio (`whisper-1`) |
| `OPENAI_MODEL_EMBEDDING` | Similarité sémantique (`text-embedding-3-large`) |

**Obtenir une nouvelle clé :** https://platform.openai.com/api-keys

**Vérifier que la clé est chargée** (backend démarré) :

```powershell
curl http://127.0.0.1:8000/health
```

Cherchez `"openai_configured": true` dans la réponse.

> **Sécurité :** ne publiez pas ce fichier sur GitHub public avec une vraie clé. Pour un dépôt partagé, utilisez une clé de test ou des variables d'environnement locales.

### Autres variables

| Variable | Description |
|----------|-------------|
| `DEBUG` | Logs détaillés si `true` |
| `SECRET_KEY` | Clé JWT — à changer en production |
| `CORS_ORIGINS` | Origines autorisées (ex. `http://localhost:5173`) |
| `DATABASE_URL` | Par défaut SQLite : `sqlite:///./data/mauritania_names.db` |
| `ELASTICSEARCH_ENABLED` | `false` par défaut (pas d'ES requis) |
| `FUZZY_THRESHOLD` | Seuil de matching flou (défaut `75`) |

Sans `OPENAI_API_KEY`, l'API démarre quand même ; les fonctionnalités IA complètes utilisent des **règles de repli** locales.

---

## Lancer le projet

Le projet nécessite **deux terminaux** : backend d'abord, puis frontend.

### Terminal 1 — Backend (API)

**PowerShell (recommandé) :**

```powershell
cd C:\Users\PC\Desktop\hack\backend
..\venv\Scripts\python.exe -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Ou avec le script fourni :**

```powershell
cd C:\Users\PC\Desktop\hack\backend
.\run.ps1
```

**Avec le venv activé :**

```powershell
cd backend
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Messages attendus :

```text
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Terminal 2 — Frontend (interface)

```powershell
cd C:\Users\PC\Desktop\hack\frontend
npm run dev
```

Messages attendus :

```text
➜  Local:   http://localhost:5173/
```

### URLs utiles

| Service | URL |
|---------|-----|
| Interface web | http://localhost:5173 |
| API (directe) | http://127.0.0.1:8000 |
| Swagger / OpenAPI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |
| Santé API | http://127.0.0.1:8000/health |

Le proxy Vite redirige automatiquement `/api`, `/health`, `/normalize-name`, `/speech-to-name` et `/live-voice-name` vers le backend.

---

## Vérification

### Santé du backend

```powershell
curl http://127.0.0.1:8000/health
```

Réponse attendue (extrait) :

```json
{
  "status": "ok",
  "database": "sqlite",
  "openai_configured": true
}
```

### Exemple — annotation document long

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/annotation/annotate/document `
  -H "Content-Type: application/json" `
  -d "{\"text\": \"Mohamed O Ahmed`nمحمد ولد أحمد`nMouhamed O Ahmed\"}"
```

*(Sous bash/Linux, utilisez `\n` dans la chaîne JSON.)*

---

## Dépannage

| Problème | Cause probable | Solution |
|----------|----------------|----------|
| `'uvicorn' n'est pas reconnu` | Uvicorn absent du venv ou `Scripts` hors PATH | `python -m pip install "uvicorn[standard]"` puis `python -m uvicorn main:app ...` |
| `Could not import module "app.main"` | Mauvais module ou mauvais répertoire | `cd backend` puis `main:app` (pas `app.main:app`) |
| `ECONNREFUSED 127.0.0.1:8000` (Vite) | Backend non démarré | Lancer le terminal backend avant `npm run dev` |
| Erreur à l'import (`sqlalchemy`, etc.) | Dépendances incomplètes | `pip install -r backend\requirements.txt` |
| `openai_configured: false` dans `/health` | Clé absente ou **commentée** (`# OPENAI_API_KEY=...`) | Enlever le `#` devant `OPENAI_API_KEY` dans `hack/.env.example`, puis redémarrer le backend |

### Commandes à ne pas utiliser

```powershell
# ❌ Depuis la racine hack/
uvicorn app.main:app --reload --port 8000

# ✅ Depuis backend/
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

---

## Innovation IA

| Capacité | Description |
|----------|-------------|
| **Long contexte** | Analyse de listes/registres administratifs, extraction de noms, clusters d'identité |
| **ICL (few-shot)** | Sélection dynamique d'exemples du dictionnaire local dans le prompt GPT |
| **Annotation auto** | Extraction → OpenAI → phonétique → fuzzy → scores confiance/doublon |
| **Mémoire adaptative** | `learned_names.py` enrichi par validation humaine |
| **Whisper** | Saisie vocale → transcription → normalisation |
| **Doublons** | Détection cross-variantes avec explication IA |

### Pipeline IA (résumé)

```
Input (texte / voix / CSV / Excel)
  → Whisper (si voix)
  → Extraction entités (noms)
  → OpenAI + ICL few-shot
  → Matching phonétique + fuzzy + embeddings
  → Détection doublons
  → Normalisation + scores
  → Validation utilisateur
  → Sauvegarde mémoire locale
```

---

## Architecture

Détail complet : [`backend/ARCHITECTURE.md`](backend/ARCHITECTURE.md).

```
React Dashboard (frontend)
        ↓  proxy Vite → :8000
NIDEngine (orchestrateur — backend/app/pipeline/nid_engine.py)
  1. Preprocessing      — nettoyage, segmentation, extraction
  2. Local Entity       — RapidFuzz, phonétique, dictionnaire
  3. AI Reasoning       — OpenAI GPT (6 étapes, pas d'invention)
  4. Validation         — anti-hallucination
  5. Clustering         — fusion ≥ 88%
  6. Identity Graph     — SQLite persistant (nodes/variants/edges)
  7. Output             — JSON strict production
        ↓
SQLite (défaut) / PostgreSQL + Elasticsearch (optionnel)
```

---

## API

### Endpoints principaux

| Fonction | Méthode | Endpoint |
|----------|---------|----------|
| Santé | `GET` | `/health` |
| Normalisation | `POST` | `/normalize-name` |
| Document structuré (production) | `POST` | `/api/v1/annotation/annotate/document/structured` |
| Annotation complète | `POST` | `/api/v1/annotation/annotate/full` |
| Document long | `POST` | `/api/v1/annotation/annotate/document` |
| Identity Graph — stats | `GET` | `/api/v1/identity-graph/stats` |
| Import batch (fichier) | `POST` | `/api/v1/annotation/annotate/upload` |
| Audio → nom | `POST` | `/speech-to-name` |
| Voix en direct | `POST` | `/live-voice-name` |
| Doublons | `GET` | `/api/v1/duplicates` |
| Apprentissage | `POST` | `/api/v1/knowledge/learn` |
| Historique / validation | `GET` / `POST` | `/api/v1/history` |
| Authentification | — | `/api/v1/auth/*` |

Documentation interactive : **http://127.0.0.1:8000/docs**

---

## Compte administrateur

Compte créé automatiquement au premier démarrage (seed) :

| Champ | Valeur |
|-------|--------|
| Utilisateur | `admin` |
| Mot de passe | `Admin@2024!` |

À modifier en production.

---

## Cas d'usage

État civil · Hôpitaux · Banques · Écoles · Administrations · Anti-fraude · Statistiques nationales

---

## Licence

Usage gouvernemental — République Islamique de Mauritanie.
