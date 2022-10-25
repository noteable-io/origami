# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Changed
- Reduce required pydantic version from ^1.9.1 to ^1.9.0

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
