"""Tests for the async noteable client calls."""

import json
from datetime import datetime
from uuid import UUID, uuid4

import pytest
from mock import AsyncMock, patch

from ..client import NoteableClient
from ..types.rtu import GenericRTUReply


def extract_msg_transaction_id(msg):
    """Helper to pull out transaction_id from json strings"""
    return UUID(json.loads(msg)['transaction_id'])


@patch('websockets.connect', new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_client_websocket_context(connect_mock):
    # The connect does a ping to ensure that the connection is healthy
    async def assign_id(msg):
        req_id = extract_msg_transaction_id(msg)
        connect_mock.return_value.recv.return_value = GenericRTUReply(
            msg_id=uuid4(),
            transaction_id=req_id,
            event='ping_reply',
            channel='system',
            processed_timestamp=datetime.now(),
        ).json()

    connect_mock.return_value.send.side_effect = assign_id

    async with NoteableClient('fake-token') as client:
        headers = {'Authorization': 'Bearer fake-token', 'Origin': client.origin}
        connect_mock.assert_called_once_with(client.ws_uri, extra_headers=headers)
        connect_mock.assert_called_once()
        connect_mock.return_value.close.assert_not_called()
    connect_mock.return_value.recv.assert_called()
    connect_mock.return_value.close.assert_called_once()
