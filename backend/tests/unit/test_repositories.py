"""Tests for repositories with strict multi-user boundary enforcement."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError, ProviderError
from app.repositories.profile_repository import ProfileRepository
from app.repositories.search_preferences_repository import SearchPreferencesRepository
from app.repositories.task_repository import TaskRepository

# ── Profile Repository ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_profile_repo_get_profile():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_query = MagicMock()
    mock_table.select.return_value = mock_query
    mock_filter = MagicMock()
    mock_query.eq.return_value = mock_filter
    mock_single = MagicMock()
    mock_filter.maybe_single.return_value = mock_single

    user_id = uuid4()
    mock_single.execute.return_value = MagicMock(
        data={"user_id": str(user_id), "display_name": "Alice"}
    )

    repo = ProfileRepository(client=mock_client)
    res = await repo.get_profile(user_id)

    assert res is not None
    assert res["display_name"] == "Alice"
    mock_table.select.assert_called_with("*")
    mock_query.eq.assert_called_with("user_id", str(user_id))


@pytest.mark.asyncio
async def test_profile_repo_get_profile_error():
    mock_client = MagicMock()
    mock_client.table.side_effect = RuntimeError("DB connection failure")

    repo = ProfileRepository(client=mock_client)
    with pytest.raises(ProviderError):
        await repo.get_profile(uuid4())


@pytest.mark.asyncio
async def test_profile_repo_upsert_profile():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_upsert = MagicMock()
    mock_table.upsert.return_value = mock_upsert

    user_id = uuid4()
    mock_upsert.execute.return_value = MagicMock(
        data=[{"user_id": str(user_id), "display_name": "Alice"}]
    )

    repo = ProfileRepository(client=mock_client)
    res = await repo.upsert_profile(user_id, {"display_name": "Alice"})

    assert res["display_name"] == "Alice"
    mock_table.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_profile_repo_create_resume_version_increments():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_order = MagicMock()
    mock_eq.order.return_value = mock_order
    mock_limit = MagicMock()
    mock_order.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(data=[{"version_number": 2}])

    mock_insert = MagicMock()
    mock_table.insert.return_value = mock_insert
    user_id = uuid4()
    mock_insert.execute.return_value = MagicMock(
        data=[{"user_id": str(user_id), "version_number": 3, "source_type": "pdf"}]
    )

    repo = ProfileRepository(client=mock_client)
    res = await repo.create_resume_version(user_id, source_type="pdf")

    assert res["version_number"] == 3


@pytest.mark.asyncio
async def test_profile_repo_get_resume_versions():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_order = MagicMock()
    mock_eq.order.return_value = mock_order

    user_id = uuid4()
    mock_order.execute.return_value = MagicMock(data=[{"version_number": 2}, {"version_number": 1}])

    repo = ProfileRepository(client=mock_client)
    versions = await repo.get_resume_versions(user_id)

    assert len(versions) == 2
    mock_select.eq.assert_called_with("user_id", str(user_id))


@pytest.mark.asyncio
async def test_profile_repo_get_resume_version_single():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_single = MagicMock()
    mock_eq2.maybe_single.return_value = mock_single

    user_id = uuid4()
    vid = uuid4()
    mock_single.execute.return_value = MagicMock(
        data={"id": str(vid), "user_id": str(user_id), "version_number": 1}
    )

    repo = ProfileRepository(client=mock_client)
    version = await repo.get_resume_version(user_id, vid)

    assert version is not None
    assert version["id"] == str(vid)


@pytest.mark.asyncio
async def test_profile_repo_update_resume_extraction():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq1 = MagicMock()
    mock_update.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2

    user_id = uuid4()
    vid = uuid4()
    mock_eq2.execute.return_value = MagicMock(
        data=[{"id": str(vid), "extraction_status": "completed"}]
    )

    repo = ProfileRepository(client=mock_client)
    res = await repo.update_resume_extraction(
        user_id, vid, status="completed", raw_text="Extracted text"
    )

    assert res["extraction_status"] == "completed"


@pytest.mark.asyncio
async def test_profile_repo_create_profile_version():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_order = MagicMock()
    mock_eq.order.return_value = mock_order
    mock_limit = MagicMock()
    mock_order.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(data=[])

    mock_insert = MagicMock()
    mock_table.insert.return_value = mock_insert
    user_id = uuid4()
    mock_insert.execute.return_value = MagicMock(data=[{"version_number": 1, "skills": ["Python"]}])

    repo = ProfileRepository(client=mock_client)
    res = await repo.create_profile_version(
        user_id=user_id,
        resume_version_id=None,
        content={"summary": "Dev"},
        skills=["Python"],
    )

    assert res["version_number"] == 1
    assert res["skills"] == ["Python"]


@pytest.mark.asyncio
async def test_profile_repo_get_active_profile_version():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    # Mock confirmed query
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_order = MagicMock()
    mock_eq2.order.return_value = mock_order
    mock_limit = MagicMock()
    mock_order.limit.return_value = mock_limit

    user_id = uuid4()
    mock_limit.execute.return_value = MagicMock(data=[{"version_number": 2, "is_confirmed": True}])

    repo = ProfileRepository(client=mock_client)
    res = await repo.get_active_profile_version(user_id)

    assert res is not None
    assert res["version_number"] == 2
    assert res["is_confirmed"] is True


@pytest.mark.asyncio
async def test_profile_repo_confirm_profile_version_success():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq1 = MagicMock()
    mock_update.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2

    vid = uuid4()
    mock_eq2.execute.return_value = MagicMock(data=[{"id": str(vid), "is_confirmed": True}])

    repo = ProfileRepository(client=mock_client)
    res = await repo.confirm_profile_version(uuid4(), vid)

    assert res["is_confirmed"] is True


@pytest.mark.asyncio
async def test_profile_repo_confirm_profile_version_not_found():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq1 = MagicMock()
    mock_update.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_eq2.execute.return_value = MagicMock(data=[])

    repo = ProfileRepository(client=mock_client)
    with pytest.raises(NotFoundError):
        await repo.confirm_profile_version(uuid4(), uuid4())


@pytest.mark.asyncio
async def test_profile_evidence_operations():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_insert = MagicMock()
    mock_table.insert.return_value = mock_insert

    user_id = uuid4()
    pvid = uuid4()
    mock_insert.execute.return_value = MagicMock(
        data=[
            {
                "id": str(uuid4()),
                "user_id": str(user_id),
                "profile_version_id": str(pvid),
                "claim_type": "skill",
                "claim_value": "Python",
                "confidence": "explicit",
            }
        ]
    )

    repo = ProfileRepository(client=mock_client)
    res = await repo.add_profile_evidence(
        user_id=user_id,
        profile_version_id=pvid,
        claim_type="skill",
        claim_value="Python",
        confidence="explicit",
    )

    assert res["claim_value"] == "Python"

    # Test get evidence
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_eq2.execute.return_value = MagicMock(data=[res])

    evidence_list = await repo.get_profile_evidence(user_id, pvid)
    assert len(evidence_list) == 1
    assert evidence_list[0]["claim_value"] == "Python"


# ── Search Preferences Repository ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_preferences_repo():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_single = MagicMock()
    mock_eq.maybe_single.return_value = mock_single

    user_id = uuid4()
    mock_single.execute.return_value = MagicMock(
        data={"user_id": str(user_id), "target_roles": ["Software Engineer"]}
    )

    repo = SearchPreferencesRepository(client=mock_client)
    prefs = await repo.get_preferences(user_id)

    assert prefs is not None
    assert prefs["target_roles"] == ["Software Engineer"]
    mock_select.eq.assert_called_with("user_id", str(user_id))

    # Test upsert
    mock_upsert = MagicMock()
    mock_table.upsert.return_value = mock_upsert
    mock_upsert.execute.return_value = MagicMock(
        data=[{"user_id": str(user_id), "target_roles": ["Backend Lead"]}]
    )

    saved = await repo.upsert_preferences(user_id, {"target_roles": ["Backend Lead"]})
    assert saved["target_roles"] == ["Backend Lead"]


# ── Task Repository ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_task_repo_enqueue_idempotency_hit():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_single = MagicMock()
    mock_eq2.maybe_single.return_value = mock_single

    user_id = uuid4()
    key = "idemp-key-123"
    mock_single.execute.return_value = MagicMock(
        data={"id": str(uuid4()), "idempotency_key": key, "status": "pending"}
    )

    repo = TaskRepository(client=mock_client)
    task = await repo.enqueue_task(
        user_id=user_id,
        task_type="search_run",
        payload={"query": "python"},
        idempotency_key=key,
    )

    assert task["idempotency_key"] == key
    mock_table.insert.assert_not_called()


@pytest.mark.asyncio
async def test_task_repo_get_task():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_single = MagicMock()
    mock_eq2.maybe_single.return_value = mock_single

    user_id = uuid4()
    tid = uuid4()
    mock_single.execute.return_value = MagicMock(
        data={"id": str(tid), "user_id": str(user_id), "status": "pending"}
    )

    repo = TaskRepository(client=mock_client)
    task = await repo.get_task(user_id, tid)

    assert task is not None
    assert task["id"] == str(tid)
    mock_select.eq.assert_called_with("user_id", str(user_id))


@pytest.mark.asyncio
async def test_task_repo_claim_next_task():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_order = MagicMock()
    mock_eq.order.return_value = mock_order
    mock_limit = MagicMock()
    mock_order.limit.return_value = mock_limit

    task_id = str(uuid4())
    mock_limit.execute.return_value = MagicMock(data=[{"id": task_id, "status": "pending"}])

    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq1 = MagicMock()
    mock_update.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_eq2.execute.return_value = MagicMock(
        data=[{"id": task_id, "status": "running", "claimed_by": "worker-1"}]
    )

    repo = TaskRepository(client=mock_client)
    claimed = await repo.claim_next_task("worker-1")

    assert claimed is not None
    assert claimed["status"] == "running"
    assert claimed["claimed_by"] == "worker-1"


@pytest.mark.asyncio
async def test_task_repo_complete_task():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table
    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq = MagicMock()
    mock_update.eq.return_value = mock_eq

    tid = uuid4()
    mock_eq.execute.return_value = MagicMock(data=[{"id": str(tid), "status": "completed"}])

    repo = TaskRepository(client=mock_client)
    res = await repo.complete_task(tid, result={"matches": 5})

    assert res["status"] == "completed"


@pytest.mark.asyncio
async def test_task_repo_fail_task_retries_and_terminal():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    # Test retry case (retry_count=0, max_retries=3)
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_single = MagicMock()
    mock_eq.maybe_single.return_value = mock_single
    mock_single.execute.return_value = MagicMock(data={"retry_count": 0, "max_retries": 3})

    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq_update = MagicMock()
    mock_update.eq.return_value = mock_eq_update
    mock_eq_update.execute.return_value = MagicMock(data=[{"status": "pending", "retry_count": 1}])

    repo = TaskRepository(client=mock_client)
    res = await repo.fail_task(uuid4(), error_message="Network glitch")

    assert res["status"] == "pending"
    assert res["retry_count"] == 1

    # Test terminal failure case (retry_count=2, max_retries=3)
    mock_single.execute.return_value = MagicMock(data={"retry_count": 2, "max_retries": 3})
    mock_eq_update.execute.return_value = MagicMock(data=[{"status": "failed", "retry_count": 2}])

    term = await repo.fail_task(uuid4(), error_message="Final failure")
    assert term["status"] == "failed"


@pytest.mark.asyncio
async def test_task_repo_recover_stale_tasks():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    # Stale query
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq = MagicMock()
    mock_select.eq.return_value = mock_eq
    mock_lt = MagicMock()
    mock_eq.lt.return_value = mock_lt

    t1 = str(uuid4())
    mock_lt.execute.return_value = MagicMock(data=[{"id": t1}])

    # Mock fail_task lookup and update for t1
    mock_single = MagicMock()
    mock_eq.maybe_single.return_value = mock_single
    mock_single.execute.return_value = MagicMock(data={"retry_count": 0, "max_retries": 3})
    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq_update = MagicMock()
    mock_update.eq.return_value = mock_eq_update
    mock_eq_update.execute.return_value = MagicMock(data=[{"status": "pending"}])

    repo = TaskRepository(client=mock_client)
    recovered = await repo.recover_stale_tasks(timeout_seconds=300)

    assert recovered == 1
