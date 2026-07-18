from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.index_status import router as index_status_router

app = FastAPI(title="vault-interview-copilot")
app.include_router(health_router)
app.include_router(index_status_router)
