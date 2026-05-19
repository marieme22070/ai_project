from fastapi import APIRouter

from app.api import annotation, auth, citizens, duplicates, history, identity_graph, knowledge, names

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(names.router, tags=["Name Standardization"])
api_router.include_router(annotation.router, prefix="/annotation", tags=["AI Annotation"])
api_router.include_router(identity_graph.router, prefix="/identity-graph", tags=["Identity Graph"])
api_router.include_router(citizens.router, prefix="/citizens", tags=["Citizens"])
api_router.include_router(history.router, prefix="/history", tags=["History"])
api_router.include_router(duplicates.router, prefix="/duplicates", tags=["Duplicates"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["Knowledge / Apprentissage"])
