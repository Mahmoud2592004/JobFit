"""Unit tests for TailoredDocumentRepository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ProviderError
from app.repositories.tailored_document_repository import TailoredDocumentRepository


@pytest.mark.asyncio
async def test_create_document_success():
    uid = uuid4()
    jid = uuid4()
    pvid = uuid4()
    mock_client = MagicMock()
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": str(uuid4()), "status": "pending"}
    ]

    repo = TailoredDocumentRepository(client=mock_client)
    res = await repo.create_document(user_id=uid, job_id=jid, profile_version_id=pvid)

    assert res["status"] == "pending"


@pytest.mark.asyncio
async def test_create_document_error():
    mock_client = MagicMock()
    mock_client.table.side_effect = Exception("DB timeout")

    repo = TailoredDocumentRepository(client=mock_client)
    with pytest.raises(ProviderError):
        await repo.create_document(user_id=uuid4(), job_id=uuid4(), profile_version_id=uuid4())


@pytest.mark.asyncio
async def test_update_document():
    uid = uuid4()
    did = uuid4()
    mock_client = MagicMock()
    mock_update = mock_client.table.return_value.update.return_value
    mock_update.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": str(did), "status": "approved"}
    ]

    repo = TailoredDocumentRepository(client=mock_client)
    res = await repo.update_document(doc_id=did, user_id=uid, updates={"status": "approved"})

    assert res is not None
    assert res["status"] == "approved"


@pytest.mark.asyncio
async def test_get_document():
    uid = uuid4()
    did = uuid4()
    mock_client = MagicMock()
    mock_select = mock_client.table.return_value.select.return_value
    mock_select.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": str(did), "user_id": str(uid)}
    ]

    repo = TailoredDocumentRepository(client=mock_client)
    res = await repo.get_document(user_id=uid, doc_id=did)

    assert res is not None
    assert res["id"] == str(did)


@pytest.mark.asyncio
async def test_list_documents_with_job():
    uid = uuid4()
    jid = uuid4()
    mock_client = MagicMock()
    mock_select = mock_client.table.return_value.select.return_value
    mock_builder = mock_select.eq.return_value.order.return_value
    mock_builder.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": str(uuid4()), "job_id": str(jid)}
    ]

    repo = TailoredDocumentRepository(client=mock_client)
    res = await repo.list_documents(user_id=uid, job_id=jid)

    assert len(res) == 1
    assert res[0]["job_id"] == str(jid)
