from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.index_status import router as index_status_router
from app.api.query import router as query_router
from app.api.retrieval_debug import router as retrieval_debug_router

app = FastAPI(title="vault-interview-copilot")
app.include_router(health_router)
app.include_router(index_status_router)
app.include_router(retrieval_debug_router)
app.include_router(query_router)
