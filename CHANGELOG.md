# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Fixed
- Fix `SessionRequestDetails.generate_file_request` to use the full file path

### Added
- `get_jupyter_server_contents` method to fetch notebook contents by path
- `update_jupyter_server_contents` method to update notebook contents by path
- `create_file_and_upload` method to create a new file and upload contents to S3 in a multipart way

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
