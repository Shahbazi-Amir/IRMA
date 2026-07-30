from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from irma.main import app
from irma.persistence.database import get_session
from irma.persistence.models import Base


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db_session:
        yield db_session
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(session: Session) -> Generator[TestClient, None, None]:
    def override_session() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
