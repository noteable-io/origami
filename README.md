# origami
A library capturing message patterns and protocols speaking to Noteable's APIs

# Connect

1. Get your access token from https://app.noteable.world/api/token
2. Test connection -

```python
from origami.client import NoteableClient

token = 'ey...' # from https://app.noteable.world/api/token
async with NoteableClient(api_token=token) as client:
    await client.ping_rtu()

>>> 2022-05-23 10:49.18 [error    ] No config object passed in and no config file found at ./auth0_config, using default empty config
    2022-05-23 10:49.18 [debug    ] Sending websocket request: transaction_id=UUID('dad3b403-fee6-401a-86f8-244e928db684') event='authenticate_request' channel='system' data=AuthenticationRequestData(token='e...')
    2022-05-23 10:49.18 [debug    ] Received websocket message: executing_user_id=None transaction_id=UUID('dad3b403-fee6-401a-86f8-244e928db684') msg_id=UUID('c13ae73d-aa4b-406e-930a-fb79611c58fc') event='authenticate_reply' channel='system' data={'success': True, 'user': {...}} processed_timestamp=datetime.datetime(2022, 5, 23, 15, 16, 11, 533877, tzinfo=datetime.timezone.utc)
    2022-05-23 10:49.18 [debug    ] Found callable for system/dad3b403-fee6-401a-86f8-244e928db684
    2022-05-23 10:49.18 [debug    ] User is authenticated!
    2022-05-23 10:49.18 [debug    ] Sending websocket request: transaction_id=UUID('3963312a-eb9a-48e6-88a8-e7a062382419') event='ping_request' channel='system' data=None
    2022-05-23 10:49.18 [debug    ] Received websocket message: executing_user_id=None transaction_id=UUID('3963312a-eb9a-48e6-88a8-e7a062382419') msg_id=UUID('72afb144-fe9d-4fbb-b746-a73ab7a865a0') event='ping_reply' channel='system' data=None processed_timestamp=datetime.datetime(2022, 5, 23, 15, 16, 11, 625892, tzinfo=datetime.timezone.utc)
    2022-05-23 10:49.18 [debug    ] Found callable for system/3963312a-eb9a-48e6-88a8-e7a062382419
    2022-05-23 10:49.18 [debug    ] Intial ping response received! Websocket is live.
```    