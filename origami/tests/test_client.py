"""Tests for the async noteable client calls."""

import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from origami.types.jobs import (
    CustomerJobDefinitionReferenceInput,
    CustomerJobInstanceReference,
    CustomerJobInstanceReferenceInput,
)

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


@pytest_asyncio.fixture
async def connect_mock():
    with patch('websockets.connect', new_callable=AsyncMock) as connect:
        yield connect


@pytest_asyncio.fixture
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


@pytest_asyncio.fixture
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


def test_token_is_loaded_from_env(client_config):
    os.environ["NOTEABLE_TOKEN"] = "fake-token-env"
    client = NoteableClient(config=client_config)
    assert client.token.access_token == "fake-token-env"


@pytest.mark.parametrize("env_name", ["NOTEABLE_URI", "NOTEABLE_DOMAIN"])
def test_domain_is_loaded_from_env(client_config, env_name):
    os.environ[env_name] = "https://example.com"
    client = NoteableClient(config=client_config)
    assert client.config.domain == "https://example.com"


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


@pytest.mark.asyncio
async def test_create_job_instance(httpx_mock, client: NoteableClient):
    job_instance_id = uuid4()
    space_id = uuid4()

    httpx_mock.add_response(
        url=f"{client.api_server_uri}/v1/customer-job-instances",
        content=CustomerJobInstanceReference(
            id=uuid4(),
            created_at=datetime.now(),
            updated_at=datetime.now(),
            customer_job_definition_reference_id=uuid4(),
        ).json(),
        match_content=json.dumps(
            {
                "orchestrator_job_instance_id": str(job_instance_id),
                "customer_job_definition_reference": {
                    "space_id": str(space_id),
                    "orchestrator_id": "dagster",
                    "orchestrator_name": "Dagster",
                    "orchestrator_job_definition_id": "my_dagster_job",
                },
            }
        ).encode("utf-8"),
    )
    await client.create_job_instance(
        CustomerJobInstanceReferenceInput(
            orchestrator_job_instance_id=str(job_instance_id),
            customer_job_definition_reference=CustomerJobDefinitionReferenceInput(
                space_id=space_id,
                orchestrator_id="dagster",
                orchestrator_name="Dagster",
                orchestrator_job_definition_id="my_dagster_job",
            ),
        )
    )


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
