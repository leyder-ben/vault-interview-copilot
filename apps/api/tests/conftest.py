import pytest
import sqlalchemy as sa

from app.core.config import settings


@pytest.fixture()
def db_engine():
    engine = sa.create_engine(settings.database_url, future=True)
    yield engine
    engine.dispose()
