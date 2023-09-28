import asyncio
import logging
import os

import typer

from origami.clients.api import APIClient
from origami.clients.rtu import RTUClient
from origami.log_utils import setup_logging

app = typer.Typer(no_args_is_help=True)


async def _get_notebook(file_id: str, api_url: str = "https://app.noteable.io/gate/api"):
    if not os.environ['NOTEABLE_TOKEN']:
        raise RuntimeError('NOTEABLE_TOKEN environment variable not set')
    api_client = APIClient(
        authorization_token=os.environ['NOTEABLE_TOKEN'],
        api_base_url=api_url,
    )
    rtu_client: RTUClient = await api_client.connect_realtime(file=file_id)
    print(rtu_client.builder.nb.json(indent=2))


@app.command()
def get(file_id: str, api_url: str = "https://app.noteable.io/gate/api"):
    asyncio.run(_get_notebook(file_id, api_url))


async def _tail_notebook(file_id: str, api_url: str = "https://app.noteable.io/gate/api"):
    if not os.environ['NOTEABLE_TOKEN']:
        raise RuntimeError('NOTEABLE_TOKEN environment variable not set')
    setup_logging()
    logging.getLogger('origami.clients.rtu').setLevel(logging.DEBUG)
    api_client = APIClient(
        authorization_token=os.environ['NOTEABLE_TOKEN'],
        api_base_url=api_url,
    )
    print("RTU Client starting initialization")
    await api_client.connect_realtime(file=file_id)
    print("RTU Client done initializing")
    while True:
        await asyncio.sleep(1)


@app.command()
def tail(file_id: str, api_url: str = "https://app.noteable.io/gate/api"):
    asyncio.run(_tail_notebook(file_id=file_id, api_url=api_url))


if __name__ == "__main__":
    app()
