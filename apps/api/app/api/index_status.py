from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.db.models import IndexRun, Note

router = APIRouter()


@router.get("/api/index/status")
def get_index_status(db: Session = Depends(get_db)) -> dict:
    latest_run = db.query(IndexRun).order_by(IndexRun.id.desc()).first()
    note_count = db.query(func.count(Note.id)).scalar()

    return {
        "embedding_model": settings.embedding_model,
        "note_count": note_count,
        "last_run": None
        if latest_run is None
        else {
            "status": latest_run.status,
            "started_at": latest_run.started_at.isoformat(),
            "completed_at": latest_run.completed_at.isoformat()
            if latest_run.completed_at
            else None,
            "files_scanned": latest_run.files_scanned,
            "files_added": latest_run.files_added,
            "files_updated": latest_run.files_updated,
            "files_deleted": latest_run.files_deleted,
            "errors": latest_run.errors_json,
        },
    }
