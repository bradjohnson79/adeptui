"""Project password protection — hashing, grants, lock enforcement."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, Project
from app.project_security import service
from app.project_security.hashing import hash_password, verify_password
from app.project_security.models import ProjectSecurityRow, ProjectUnlockGrantRow


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # Ensure security tables
    from app.project_security import models as _m  # noqa: F401

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Project(id="proj-a", name="Alpha"))
    session.add(Project(id="proj-b", name="Beta"))
    session.commit()
    yield session
    session.close()


def test_hash_never_plaintext():
    stored = hash_password("correct horse battery staple")
    assert stored["password_hash"]
    assert "correct horse" not in stored["password_hash"]
    assert stored["password_algorithm"] in ("argon2id", "pbkdf2_sha256")
    assert verify_password(
        "correct horse battery staple",
        password_hash=stored["password_hash"],
        algorithm=stored["password_algorithm"],
        params=stored["password_params"],
    )
    assert not verify_password(
        "wrong password here!!",
        password_hash=stored["password_hash"],
        algorithm=stored["password_algorithm"],
        params=stored["password_params"],
    )


def test_enable_unlock_lock_change(db):
    service.enable_password(
        db,
        "proj-a",
        password="correct horse battery staple",
        confirm_password="correct horse battery staple",
        password_hint="animal power",
    )
    row = db.get(ProjectSecurityRow, "proj-a")
    assert row and row.password_protected == 1
    assert row.password_hash
    assert "staple" not in (row.password_hash or "")

    with pytest.raises(Exception):
        service.unlock(db, "proj-a", password="definitely wrong!!")

    out = service.unlock(db, "proj-a", password="correct horse battery staple", remember_for="15m")
    token = out["unlockToken"]
    assert token
    assert service.is_unlocked(db, "proj-a", token)

    # Cross-project grant denied when B is also protected
    service.enable_password(
        db,
        "proj-b",
        password="other project passphrase!",
        confirm_password="other project passphrase!",
    )
    assert not service.is_unlocked(db, "proj-b", token)

    service.lock_now(db, "proj-a")
    assert not service.is_unlocked(db, "proj-a", token)

    # change_password verifies current password and revokes grants
    service.change_password(
        db,
        "proj-a",
        current_password="correct horse battery staple",
        new_password="new long passphrase xx",
        confirm_password="new long passphrase xx",
    )
    assert not service.is_unlocked(db, "proj-a", token)
    out2 = service.unlock(db, "proj-a", password="new long passphrase xx")
    assert out2["unlockToken"] != token


def test_disable_and_audit(db):
    service.enable_password(
        db,
        "proj-a",
        password="correct horse battery staple",
        confirm_password="correct horse battery staple",
    )
    service.disable_password(
        db,
        "proj-a",
        current_password="correct horse battery staple",
        confirm=True,
    )
    assert not service.is_protected(db, "proj-a")
    from app.project_security.audit import list_audit

    events = {e["event"] for e in list_audit(db, "proj-a")}
    assert "project_password_enabled" in events
    assert "project_password_disabled" in events


def test_duplicate_fresh_hash(db):
    service.enable_password(
        db,
        "proj-a",
        password="correct horse battery staple",
        confirm_password="correct horse battery staple",
    )
    src = db.get(ProjectSecurityRow, "proj-a")
    assert src
    old_hash = src.password_hash
    service.apply_duplicate_protection(
        db,
        source_project_id="proj-a",
        new_project_id="proj-b",
        mode="new_password",
        password="correct horse battery staple",
        confirm_password="correct horse battery staple",
    )
    db.commit()
    dup = db.get(ProjectSecurityRow, "proj-b")
    assert dup and dup.password_protected == 1
    assert dup.password_hash != old_hash


def test_gate_binary():
    from app.project_security.production_gate import evaluate_project_password_protection_gate

    g = evaluate_project_password_protection_gate()
    assert "projectPasswordProtectionGo" in g
    assert g["binaryOnly"] is True
    assert g["conditionalGoForbidden"] is True
