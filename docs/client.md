# Noteable Client

The NoteableClient class provides an extension of `httpx.AsyncClient` with Noteable specific helpers. The async entrypoint for the class will establish and maintain a websocket for real time updates to/from Noteable servers. The API messages being sent have custom formats from Jupyter but for any directly connecting to the kernel pass Jupyter messages across the Noteable API layer. e.g. observing output messages arriving you'll see that their content matches the ZMQ Jupyter format.

## Authentication

The client automatically uses the `api_token` argument, or the `NOTEABLE_TOKEN` environment variable in absence, to generate the `f"Bearer {self.token.access_token}"` to establish connections or REST requests. This token can be an ephemeral token fetched dynamically from the site live with a short lifecycle, or you can create a more permanent token via your User Settings in the upper right of the Noteable platform. Either one will work as a Bearer token for authentication and can be individually revoked as needed.

Note: If you have a custom deployment URL for your Noteable service, you'll need to set the `NOTEABLE_DOMAIN` environment variable or the `domain` config key to point to the correct URL. Otherwise it will default to the public multi-tenant environment.

## Routes

Most routes presented help with kernel session or file manipulation. Some direct Jupyter APIs are also present on the server but not given helpers in the client as there's often a wrapping API preferred for use or replacing the open source pattern with Noteable specific affordances.

`get_or_launch_ready_kernel_session` is often where one will start to initiate or join a kernel session, handling the launch handshakes and establishing a connection to the Jupyter kernel. See the [API docs page](/reference/client/#client.NoteableClient.get_or_launch_ready_kernel_session) for the specific method signatures.

You don't need to explicitly call `delete_kernel_session` but it does save on resources being utilized until they timeout on the service side. If you know you're wrapping up an interactions it's polite to clean the kernel and avoid wasting money / carbon.

## Websockets

Once aentered, the client will stream all messages back from the real time update channels. You can use `register_message_callback` to setup your own callbacks based on `message_type`, `transaction_id`, or response schemas. This is the primary way to respond to events in Noteable.

Similarly, `send_rtu_request` is used to initiate any real time requests to the system. Common patterns using these calls are wrapped in helpers to achieve known patterns but any extensions can be added to customize client behavior using these mechanisms.

See the [API docs page](/reference/client/) for the specific method signatures related to these actions.