"""Unit tests for ApplicationRepository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ProviderError
from app.repositories.application_repository import ApplicationRepository


@pytest.mark.asyncio
async def test_create_application_success():
    mock_client = MagicMock()
    mock_table_apps = MagicMock()
    mock_table_events = MagicMock()

    def table_router(table_name: str):
        if table_name == "applications":
            return mock_table_apps
        return mock_table_events

    mock_client.table.side_effect = table_router

    user_id = uuid4()
    job_id = uuid4()
    app_id = str(uuid4())

    mock_upsert = MagicMock()
    mock_table_apps.upsert.return_value = mock_upsert
    mock_upsert.execute.return_value = MagicMock(
        data=[
            {
                "id": app_id,
                "user_id": str(user_id),
                "job_id": str(job_id),
                "status": "saved",
                "notes": "Interested",
                "created_at": "2026-10-10T00:00:00Z",
                "updated_at": "2026-10-10T00:00:00Z",
            }
        ]
    )

    mock_insert_event = MagicMock()
    mock_table_events.insert.return_value = mock_insert_event
    mock_insert_event.execute.return_value = MagicMock(
        data=[
            {
                "id": str(uuid4()),
                "application_id": app_id,
                "user_id": str(user_id),
                "to_status": "saved",
                "from_status": None,
                "note": "Initial tracking",
                "occurred_at": "2026-10-10T00:00:00Z",
            }
        ]
    )

    repo = ApplicationRepository(client=mock_client)
    res = await repo.create_application(
        user_id=user_id,
        job_id=job_id,
        status="saved",
        notes="Interested",
    )

    assert res["id"] == app_id
    assert res["status"] == "saved"
    mock_table_apps.upsert.assert_called_once()
    mock_table_events.insert.assert_called_once()


@pytest.mark.asyncio
async def test_create_application_error():
    mock_client = MagicMock()
    mock_client.table.side_effect = RuntimeError("DB connection failure")

    repo = ApplicationRepository(client=mock_client)
    with pytest.raises(ProviderError):
        await repo.create_application(user_id=uuid4(), job_id=uuid4())


@pytest.mark.asyncio
async def test_update_application_success():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    user_id = uuid4()
    app_id = uuid4()

    mock_update = MagicMock()
    mock_table.update.return_value = mock_update
    mock_eq1 = MagicMock()
    mock_update.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_eq2.execute.return_value = MagicMock(
        data=[{"id": str(app_id), "user_id": str(user_id), "status": "applied"}]
    )

    repo = ApplicationRepository(client=mock_client)
    res = await repo.update_application(
        user_id=user_id,
        application_id=app_id,
        updates={"status": "applied"},
    )

    assert res is not None
    assert res["status"] == "applied"
    mock_table.update.assert_called_once()


@pytest.mark.asyncio
async def test_update_application_not_found():
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

    repo = ApplicationRepository(client=mock_client)
    res = await repo.update_application(
        user_id=uuid4(),
        application_id=uuid4(),
        updates={"status": "interviewing"},
    )

    assert res is None


@pytest.mark.asyncio
async def test_get_application_success():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    user_id = uuid4()
    app_id = uuid4()

    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_limit = MagicMock()
    mock_eq2.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(
        data=[{"id": str(app_id), "user_id": str(user_id), "status": "saved"}]
    )

    repo = ApplicationRepository(client=mock_client)
    res = await repo.get_application(user_id=user_id, application_id=app_id)

    assert res is not None
    assert res["id"] == str(app_id)


@pytest.mark.asyncio
async def test_get_application_not_found():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_limit = MagicMock()
    mock_eq2.limit.return_value = mock_limit
    mock_limit.execute.return_value = MagicMock(data=[])

    repo = ApplicationRepository(client=mock_client)
    res = await repo.get_application(user_id=uuid4(), application_id=uuid4())

    assert res is None


@pytest.mark.asyncio
async def test_list_applications_success():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_order = MagicMock()
    mock_eq1.order.return_value = mock_order
    mock_eq_status = MagicMock()
    mock_order.eq.return_value = mock_eq_status
    mock_range = MagicMock()
    mock_eq_status.range.return_value = mock_range
    mock_range.execute.return_value = MagicMock(data=[{"id": str(uuid4()), "status": "applied"}])

    repo = ApplicationRepository(client=mock_client)
    res = await repo.list_applications(user_id=uuid4(), status="applied", limit=10, offset=0)

    assert len(res) == 1
    assert res[0]["status"] == "applied"


@pytest.mark.asyncio
async def test_add_and_list_application_events():
    mock_client = MagicMock()
    mock_table = MagicMock()
    mock_client.table.return_value = mock_table

    app_id = uuid4()
    user_id = uuid4()

    mock_insert = MagicMock()
    mock_table.insert.return_value = mock_insert
    mock_insert.execute.return_value = MagicMock(
        data=[
            {
                "id": str(uuid4()),
                "application_id": str(app_id),
                "user_id": str(user_id),
                "to_status": "applied",
                "note": "Applied via site",
                "occurred_at": "2026-10-10T00:00:00Z",
            }
        ]
    )

    repo = ApplicationRepository(client=mock_client)
    event = await repo.add_application_event(
        application_id=app_id,
        user_id=user_id,
        to_status="applied",
        note="Applied via site",
    )
    assert event["to_status"] == "applied"

    # Test list events
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_order = MagicMock()
    mock_eq2.order.return_value = mock_order
    mock_order.execute.return_value = MagicMock(data=[event])

    events = await repo.list_application_events(user_id=user_id, application_id=app_id)
    assert len(events) == 1
    assert events[0]["note"] == "Applied via site"
