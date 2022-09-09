# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
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
