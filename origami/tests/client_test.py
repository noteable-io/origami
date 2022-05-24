"""Tests for the async noteable client calls."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from boto import config

from ..client import ClientConfig, NoteableClient
from ..types.rtu import (
    AuthenticationReply,
    FileSubscribeActionReplyData,
    FileSubscribeReplySchema,
    GenericRTUReply,
    PingReply,
)


def extract_msg_transaction_id(msg):
    """Helper to pull out transaction_id from json strings"""
    return UUID(json.loads(msg)['transaction_id'])


@pytest.fixture
async def connect_mock():
    with patch('websockets.connect', new_callable=AsyncMock) as connect:
        yield connect


@pytest.fixture
async def connect_mock_with_auth_patched(connect_mock):
    # Initially mock our auth request
    async def auth_reply(msg):
        req_id = extract_msg_transaction_id(msg)
        connect_mock.return_value.recv.return_value = GenericRTUReply(
            msg_id=uuid4(),
            transaction_id=req_id,
            event='authenticate_reply',
            channel='system',
            data={"success": True},
            processed_timestamp=datetime.now(),
        ).json()

    connect_mock.return_value.send.side_effect = auth_reply
    yield connect_mock


@pytest.fixture
def client_config():
    return ClientConfig(domain="fake-domain")


@pytest.fixture
async def client(connect_mock_with_auth_patched, client_config):
    async with NoteableClient('fake-token', config=client_config) as client:
        yield client


@pytest.mark.asyncio
async def test_client_websocket_context(connect_mock_with_auth_patched):
    async with NoteableClient('fake-token') as client:
        headers = {'Authorization': 'Bearer fake-token', 'Origin': client.origin}
        connect_mock_with_auth_patched.assert_called_once_with(client.ws_uri, extra_headers=headers)
        connect_mock_with_auth_patched.return_value.recv.assert_called()
        connect_mock_with_auth_patched.return_value.close.assert_not_called()
    connect_mock_with_auth_patched.return_value.recv.assert_called()
    connect_mock_with_auth_patched.return_value.close.assert_called_once()


@pytest.mark.asyncio
async def test_client_ping(connect_mock, client):
    # The connect does a ping to ensure that the connection is healthy
    async def ping_reply(msg):
        req_id = extract_msg_transaction_id(msg)
        connect_mock.return_value.recv.return_value = PingReply(
            msg_id=uuid4(),
            transaction_id=req_id,
            event='ping_reply',
            channel='system',
            processed_timestamp=datetime.now(),
        ).json()

    connect_mock.return_value.send.side_effect = ping_reply

    pong = await client.ping_rtu()
    assert pong.event == 'ping_reply'


@pytest.mark.asyncio
async def test_client_subscribe(connect_mock, client):
    # The connect does a ping to ensure that the connection is healthy
    async def sub_reply(msg):
        req_id = extract_msg_transaction_id(msg)
        connect_mock.return_value.recv.return_value = AuthenticationReply(
            msg_id=uuid4(),
            transaction_id=req_id,
            event='subscribe_reply',
            channel='fake-channel',
            data={"success": True},
            processed_timestamp=datetime.now(),
        ).json()

    connect_mock.return_value.send.side_effect = sub_reply

    resp = await client.subscribe_channel('fake-channel')
    assert resp.data.success == True
    assert resp.channel == 'fake-channel'


@pytest.mark.xfail(
    reason="AttributeError: 'str' object has no attribute 'current_version_id' in client.subscribe_file"
)
@pytest.mark.asyncio
async def test_file_subscribe(connect_mock, client):
    # The connect does a ping to ensure that the connection is healthy
    async def sub_reply(msg):
        req_id = extract_msg_transaction_id(msg)
        connect_mock.return_value.recv.return_value = FileSubscribeReplySchema(
            msg_id=uuid4(),
            transaction_id=req_id,
            event='subscribe_reply',
            channel='files/fake-id',
            data=FileSubscribeActionReplyData(
                success=True, user_subscriptions=[], deltas_to_apply=[], cell_state=[]
            ),
            processed_timestamp=datetime.now(),
        ).json()

    connect_mock.return_value.send.side_effect = sub_reply

    resp = await client.subscribe_file('fake-id')
    assert resp.data.success == True
    assert resp.channel == 'files/fake-id'
    assert resp.channel in client.subscriptions
