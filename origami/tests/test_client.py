"""Tests for the async noteable client calls."""
import asyncio
import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import nbformat.v4
import pytest
import pytest_asyncio

from origami.defs.jobs import (
    CustomerJobDefinitionReferenceInput,
    CustomerJobInstanceReference,
    CustomerJobInstanceReferenceInput,
)

from ..client import ClientConfig, NoteableClient
from ..defs.files import NotebookFile
from ..defs.rtu import (
    AuthenticationReply,
    FileDeltaReply,
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


async def test_client_websocket_context(connect_mock_with_auth_patched, client_config):
    async with NoteableClient('fake-token') as client:
        headers = {'Authorization': 'Bearer fake-token', 'Origin': client.origin}
        connect_mock_with_auth_patched.assert_called_once_with(
            client.ws_uri, extra_headers=headers, open_timeout=client_config.ws_timeout
        )
        connect_mock_with_auth_patched.return_value.recv.assert_called()
        connect_mock_with_auth_patched.return_value.close.assert_not_called()
    connect_mock_with_auth_patched.return_value.recv.assert_called()
    connect_mock_with_auth_patched.return_value.close.assert_called_once()


def test_token_is_loaded_from_env():
    os.environ["NOTEABLE_TOKEN"] = "fake-token-env"
    client_config = ClientConfig()
    client = NoteableClient(config=client_config)
    assert client.config.token == "fake-token-env"


def test_domain_is_loaded_from_env():
    os.environ["NOTEABLE_DOMAIN"] = "https://example.com"
    client_config = ClientConfig()
    client = NoteableClient(config=client_config)
    assert client.config.domain == "https://example.com"


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


async def test_add_cell_doesnt_fail_on_new_delta_event(connect_mock, client, file: NotebookFile):
    """Tests that add_cell doesn't fail if it receives a new delta event before
    a new delta reply"""

    async def reply(msg):
        req_id = extract_msg_transaction_id(msg)
        connect_mock.return_value.recv.side_effect = [
            GenericRTUReply(
                event="new_delta_event",
                channel=f"files/{file.id}",
                transaction_id=req_id,
                msg_id=uuid4(),
                data={},
                processed_timestamp=datetime.now(),
            ).json(),
            FileDeltaReply(
                event="new_delta_reply",
                channel=f"files/{file.id}",
                # Callback is not checked against transaction_id so this can be anything
                transaction_id=req_id,
                msg_id=uuid4(),
                data={"success": True},
                processed_timestamp=datetime.now(),
            ).json(),
        ]

    connect_mock.return_value.send.side_effect = reply

    try:
        resp = await client.add_cell(
            file, cell=nbformat.v4.new_code_cell(source="print('hello world')"), after_id=None
        )
        assert resp.data.success
        assert resp.channel == f"files/{file.id}"
    except asyncio.TimeoutError:
        pytest.fail("add_cell timed out -- possibly due to an unexpected callback failure")

    assert not client.process_task_loop.done()


@pytest.fixture
def mock_rtu_socket():
    mock_rtu_socket = AsyncMock()
    mock_rtu_socket.recv.return_value = AsyncMock()
    return mock_rtu_socket


@pytest.fixture
def noteable_client(mock_rtu_socket):
    noteable_client = NoteableClient()
    noteable_client._connect_rtu_socket = AsyncMock()
    noteable_client.authenticate = AsyncMock()
    noteable_client.rtu_socket = mock_rtu_socket

    return noteable_client


async def test_setting_callback_result_on_cancelled_future_does_not_break_process_loop(
    noteable_client, mock_rtu_socket
):
    """Test that when a callback result is set on a cancelled future, it does not break the process loop"""

    async def callback(msg):
        return msg

    with noteable_client as nc:
        tracker = nc.register_message_callback(
            callback,
            channel="fake-channel",
            message_type="new_delta_reply",
        )

        # Let's imagine that we sent a request over RTU

        # Let's wait for response to come in and then timeout,
        # which should cancel the tracker.next_trigger future.
        try:
            await asyncio.wait_for(tracker.next_trigger, 1)
        except asyncio.TimeoutError:
            pass

        # Simulate a response coming in
        mock_rtu_socket.recv.return_value = GenericRTUReply(
            msg_id=uuid4(),
            transaction_id=uuid4(),
            event="new_delta_reply",
            channel="fake-channel",
            data={"success": True},
            processed_timestamp=datetime.now(),
        ).json()

        # Let the _process_messages task run and handle the response
        await asyncio.sleep(1)

        # At this point, the callback should have been called
        # and the process_task_loop should not have broken
        assert not nc.process_task_loop.done()
