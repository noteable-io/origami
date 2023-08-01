# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

For pre-1.0 releases, see [0.0.35 Changelog](https://github.com/noteable-io/origami/blob/0.0.35/CHANGELOG.md)

## [Unreleased]

## [1.0.0-alpha.3] - 2023-08-01
### Added
- `origami.models.notebook.make_sql_cell` convenience function, returns a `CodeCell` with appropriate metadata
- `rtu_client.change_cell_type` to switch between code, markdown, and sql cells

### Changed
 - `rtu_client.queue_execution` will always return a dict of {Future: cell_id}, even on single cell execution. Also guards against executing empty code cells

## [1.0.0-alpha.2] - 2023-07-26
### Changed
- `api_client.rtu_client` method renamed to `api_client.connect_realtime`, can accept `File` model in addition to `str` / `UUID`

## [1.0.0-alpha.1] - 2023-07-25
### Added
 - `APIClient` and `RTUClient` for HTTP and Websocket connections to Noteables API respectively
 - Discriminated-union Pydantic modeling for RTU and Delta payloads
 - End-to-end tests to run against a Noteable deployment