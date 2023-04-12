# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
## [0.0.23] - 2023-04-12
## Fixed
- Fixed `NoteableClient.add_cell` callback to look explicity for `new_delta_reply` message type, instead of by transaction_id. This is because if the `new_delta_event` message is received before the `new_delta_reply`, the `add_call` success callback will fail due to schema validation error.

## Changed
- Configured `pytest-asyncio` in `pyproject.toml` to set the `asyncio_mode` to "auto".
- Increase `ClientConfig.ws_timeout` from 10s to 60s
- Set `open_timeout` on `websockets.connect` in `NoteableClient._connect_rtu_socket`

## [0.0.23] - 2023-04-04
## Fixed
- Check whether `next_trigger` future is canceled before setting exception on it, which raises an `asyncio.InvalidStateError` if the future is already canceled.
- Retry websocket connection on `ConnectionClosedOK` and `ConnectionClosedError` errors.
- Fix the place where we reset `reconnect_rtu_task` to None

## Changed
- Removed `anonymous` role from `AccessLevel` enum
- Removed `either_raw_or_url` validator from `KernelOutputContent`

## [0.0.22] - 2023-03-28
### Changed
- Allow any list of strings as actions allowed/denied in `ResourceData` model. This is to allow for new actions that may be added in the future and avoid having to update the enum here every time.

## [0.0.21] - 2023-03-14
### Added
- Added `manage_public_output_collection` to `AccessLevelAction` enum

## [0.0.20] - 2023-03-01
### Changed
- Upgrade dependencies

## [0.0.19] - 2023-02-21
### Removed
- Removed `is_playground_mode_file` field from `NotebookFile` model

## [0.0.18] - 2023-01-06
### Fixed
- Fixed a bug where we would try to set a result/exception on future that was already cancelled due to timeout, which would cause the process_messages loop to crash.

## [0.0.17] - 2023-01-04
### Added
- Handle websocket ConnectionClosedErrors in the process messages infinite loop:
  - reconnect to the RTU websocket
  - handle authentication
  - resubscribe to all the previously subscribed channels
- Add backoff retry to `send_rtu_request` when a `ConnectionClosedError` is raised, and reconnect to RTU before retrying.
- Add backoff retry to `update_job_instance` on `ReadTimeout` error
- Add backoff retry to `get_or_launch_ready_kernel_session` on `TimeoutError`.

## [0.0.16] - 2022-12-02
### Fixed
- Fix API incompatibility when creating a parameterized notebook

## [0.0.15] - 2022-11-18
### Added
- Added `update_job_instance` client method

### Changed
- Refactor create_parameterized_notebook to include job instance attempt information

## [0.0.13] - 2022-11-03
### Added
- Use `backend_path` config value when making API requests to Noteable

## [0.0.12] - 2022-11-03
### Added
- Allow user to specify http & websocket protocol for client
  - Generally want to use https and wss but for local development, http/ws is useful

## [0.0.11] - 2022-11-01
### Fixed
- Fixed documentation build reference

### Added
- Added `update_job_instance_attempt` to `AccessLevelAction` enum

## [0.0.10] - 2022-11-01
### Changed
- `types` submodule renamed to `defs`

## [0.0.9] - 2022-10-28
### Changed
- Reduce required pydantic version from ^1.9.1 to ^1.9.0
- Remove deprecated `NOTEABLE_URI` environment variable

## [0.0.8] - 2022-10-26
### Added
- Add types for display handler updates

## [0.0.7] - 2022-10-20
### Added
- Add client methods for `update_cell_metadata` and `update_nb_metadata`
- Add retry to `launch_kernel_session`

## [0.0.6] - 2022-10-05
### Added
- Add `__enter__` and `__exit__` methods to `NoteableClient` to allow it to be used as a synchronous context manager
- Read `bulk_cell_state_update_event` messages for cell state instead of `cell_state_update_event`
- Add `rename` to `AccessLevelActions` enum

## [0.0.5] - 2022-09-13
### Added
- Add kernel output types for papermill-origami

## [0.0.4] - 2022-09-09
### Added
- Support loading JWT token from `NOTEABLE_TOKEN` environment variable.
- Support loading API domain from `NOTEABLE_URL` or `NOTEABLE_DOMAIN` environment variable.
- Add `create_parameterized_notebook` method to `NoteableClient`
- Add `create_job_instance` method to `NoteableClient`

## [0.0.3] - 2022-09-02
### Fixed
- Fix `SessionRequestDetails.generate_file_request` handling of file paths with folders

### Added
- Add ability to delete/add cells with NoteableClient

## [0.0.2] - 2022-08-02
### Changed
- Change `name` in pyproject.toml from `origami` to `noteable-origami`
- Disable tag generation by bumpversion

### Added
- Add `packages` to pyproject.toml

### Removed
- Remove `tool.poetry.source` config from pyproject.toml

## [0.0.1] - 2022-08-02
### Added
- Initial setup
