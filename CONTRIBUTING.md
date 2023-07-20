# Contributing

When contributing to this repository, please first discuss the change you wish to make via issue,
email, or any other method with the owners of this repository before making a change. 

Please note we have a [code of conduct](./CODE_OF_CONDUCT.md), please follow it in all your interactions with the project.

## Pull Request Process

1. Ensure tests pass before submitting a pull request.
1. For non-trivial changes, ensure new tests are present before submitting a pull request.
1. Update the README.md with details of changes to the interface, this includes new environment 
   variables, exposed ports, useful file locations and container parameters.
1. You may merge the Pull Request in once you have the sign-off of one other developer, or if you 
   do not have permission to do that, you may request the reviewer to merge it for you.

## Local setup

1. Fork this repository.
2. Clone the forked repository.
3. Change to the cloned directory.
4. Ensure [`poetry`](https://python-poetry.org/docs/#installation) is installed.
5. Run `poetry install`.
6. Run `nox -s test` to run all tests.

## Project layout

The project strucute follows this pattern:

```
   pyproject.toml # The repository toml for setup instructions
   mkdocs.yml     # Docs configuration file
   docs/
      index.md    # The documentation homepage.
      ...         # Other markdown pages, images and other files
   tests/
      ...         # End-to-end tests against a Noteable cluster
   origami/
      clients/
         api.py    # HTTP API Client for CRUD resources
         rtu.py    # RTU Client for live Notebook document model updates and cell execution
         cache.py  # RTU Client cache for interacting with multiple Notebooks
      models/
         rtu/      # Real-time-update websocket payload models
         deltas/   # Document model updates within RTU Delta payloads
      notebook/
         ...       # In-memory Notebook builder that squashes RTU/Deltas
```