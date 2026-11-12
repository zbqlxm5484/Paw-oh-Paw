"""DB 연결 상한(11.7, S15P31A404-274). API는 스레드 수와 같은 40개, 워커는 10개다."""

import functools

import pytest
from sqlalchemy.engine import Engine

from app.core import db


def _fresh_engine_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    """이 시험만 쓰는 get_engine을 끼운다. 다른 시험이 쓰는 엔진과 상한 값은 건드리지 않는다."""
    monkeypatch.setattr(db, "get_engine", functools.lru_cache(db.get_engine.__wrapped__))
    monkeypatch.setattr(db, "_pool_limits", (db.POOL_SIZE, db.POOL_MAX_OVERFLOW))


def _limits(engine: Engine) -> tuple[int, int]:
    return engine.pool.size(), engine.pool._max_overflow


def test_api_engine_allows_as_many_connections_as_request_threads(monkeypatch: pytest.MonkeyPatch) -> None:
    _fresh_engine_factory(monkeypatch)
    engine = db.get_engine()
    try:
        assert _limits(engine) == (20, 20)  # 20 + 20 = 스레드 40개
    finally:
        engine.dispose()


def test_worker_lowers_the_limit_before_the_engine_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    _fresh_engine_factory(monkeypatch)
    db.use_worker_pool()
    engine = db.get_engine()
    try:
        assert _limits(engine) == (5, 5)
        # 상한끼리 더해도 API 두 벌(배포 전환 중)과 워커가 PostgreSQL 기본 max_connections(100) 안이다
        api = db.POOL_SIZE + db.POOL_MAX_OVERFLOW
        assert 2 * api + sum(_limits(engine)) <= 100
    finally:
        engine.dispose()


def test_lowering_the_limit_after_the_engine_exists_is_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _fresh_engine_factory(monkeypatch)
    engine = db.get_engine()
    try:
        with pytest.raises(RuntimeError):
            db.use_worker_pool()
        assert db._pool_limits == (db.POOL_SIZE, db.POOL_MAX_OVERFLOW)
    finally:
        engine.dispose()
