"""Unit tests for JobMatchRepository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ProviderError
from app.repositories.job_match_repository import JobMatchRepository


@pytest.mark.asyncio
async def test_upsert_match_success():
    mock_client = MagicMock()
    mock_upsert = MagicMock()
    mock_client.table.return_value.upsert.return_value = mock_upsert
    mock_upsert.execute.return_value.data = [
        {"id": str(uuid4()), "overall_score": 88.0, "scoring_version": "v1.0.0"}
    ]

    repo = JobMatchRepository(client=mock_client)
    res = await repo.upsert_match(
        user_id=uuid4(),
        job_id=uuid4(),
        scoring_version="v1.0.0",
        overall_score=88.0,
        score_breakdown={"skills_score": 90.0},
        matching_evidence=["Evidence"],
        missing_requirements=[],
        uncertain_factors=[],
    )

    assert res["overall_score"] == 88.0


@pytest.mark.asyncio
async def test_upsert_match_error():
    mock_client = MagicMock()
    mock_client.table.side_effect = Exception("DB error")

    repo = JobMatchRepository(client=mock_client)
    with pytest.raises(ProviderError):
        await repo.upsert_match(
            user_id=uuid4(),
            job_id=uuid4(),
            scoring_version="v1.0.0",
            overall_score=88.0,
            score_breakdown={},
            matching_evidence=[],
            missing_requirements=[],
            uncertain_factors=[],
        )


@pytest.mark.asyncio
async def test_get_match_success():
    uid = uuid4()
    mid = uuid4()
    mock_client = MagicMock()
    mock_select = mock_client.table.return_value.select.return_value
    mock_select.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": str(mid), "user_id": str(uid)}
    ]

    repo = JobMatchRepository(client=mock_client)
    res = await repo.get_match(user_id=uid, match_id=mid)

    assert res is not None
    assert res["id"] == str(mid)


@pytest.mark.asyncio
async def test_get_match_by_job():
    uid = uuid4()
    jid = uuid4()
    mock_client = MagicMock()
    mock_select = mock_client.table.return_value.select.return_value
    mock_builder = mock_select.eq.return_value.eq.return_value.eq.return_value
    mock_builder.limit.return_value.execute.return_value.data = [
        {"id": str(uuid4()), "job_id": str(jid)}
    ]

    repo = JobMatchRepository(client=mock_client)
    res = await repo.get_match_by_job(user_id=uid, job_id=jid)

    assert res is not None
    assert res["job_id"] == str(jid)


@pytest.mark.asyncio
async def test_list_matches_with_filters():
    uid = uuid4()
    mock_client = MagicMock()
    mock_builder = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value = (
        mock_builder
    )
    mock_builder.gte.return_value = mock_builder
    mock_builder.eq.return_value = mock_builder
    mock_builder.range.return_value.execute.return_value.data = [
        {"id": str(uuid4()), "overall_score": 95.0}
    ]

    repo = JobMatchRepository(client=mock_client)
    res = await repo.list_matches(user_id=uid, min_score=80.0, is_saved=True)

    assert len(res) == 1
    assert res[0]["overall_score"] == 95.0


@pytest.mark.asyncio
async def test_set_saved_status():
    uid = uuid4()
    mid = uuid4()
    mock_client = MagicMock()
    mock_update = mock_client.table.return_value.update.return_value
    mock_update.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": str(mid), "is_saved": True}
    ]

    repo = JobMatchRepository(client=mock_client)
    res = await repo.set_saved_status(user_id=uid, match_id=mid, is_saved=True)

    assert res is not None
    assert res["is_saved"] is True
