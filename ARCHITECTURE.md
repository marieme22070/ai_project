# N-ID — Architecture (7 couches)

```
                    POST /api/v1/annotation/annotate/document/structured
                                        │
                                        ▼
                              ┌─────────────────┐
                              │    NIDEngine    │
                              └────────┬────────┘
                                       │
     ┌────────────┬────────────┬──────┴──────┬────────────┬────────────┐
     ▼            ▼            ▼             ▼            ▼            ▼
┌─────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌─────────┐
│ 1. PRE  │ │ 2. LOCAL │ │ 3. GPT   │ │ 4. VALID  │ │ 5. CLUSTER│ │ 6. GRAPH│
│ process │ │  entity  │ │ reasoning│ │ anti-hall │ │  ≥88%    │ │ memory  │
└─────────┘ └──────────┘ └──────────┘ └───────────┘ └──────────┘ └────┬────┘
                                                                       │
                                                                       ▼
                                                              ┌─────────────┐
                                                              │ 7. OUTPUT   │
                                                              │ JSON strict │
                                                              └─────────────┘
```

## Modules

| Couche | Module |
|--------|--------|
| 1 | `app/layers/preprocessing.py` |
| 2 | `app/layers/local_entity_engine.py` |
| 3 | `app/layers/ai_reasoning.py` |
| 4 | `app/layers/validation.py` |
| 5 | `app/layers/clustering.py` |
| 6 | `app/identity_graph/service.py` |
| 7 | `app/layers/output_formatter.py` |

Orchestrateur : `app/pipeline/nid_engine.py`

## Stockage Identity Graph (SQLite)

- `identity_nodes` — personnes (forme canonique)
- `identity_variants` — occurrences textuelles
- `identity_edges` — liens entre nœuds (doublons probables)

API : `GET /api/v1/identity-graph/stats`

## Règles

- Pas d'entités inventées (validation couche 4)
- Fusion cluster uniquement si similarité ≥ 88%
- GPT = raisonnement uniquement, pas extraction primaire
