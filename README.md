# Origami

<p align="center">
<img src="docs/papersnake.svg" width="250px" />
<br />
Launch, edit, and share Jupyter notebooks <i>in automation</i>.
</p>

<p align="center">
<a href="https://github.com/noteable-io/origami/actions/workflows/ci.yaml">
    <img src="https://github.com/noteable-io/origami/actions/workflows/ci.yaml/badge.svg" alt="CI" />
</a>
<a href="https://codecov.io/gh/noteable-io/origami" > 
 <img src="https://codecov.io/gh/noteable-io/origami/branch/main/graph/badge.svg" alt="codecov code coverage"/> 
 </a>
<img alt="PyPI - License" src="https://img.shields.io/pypi/l/noteable-origami" />
<img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/noteable-origami" />
<img alt="PyPI" src="https://img.shields.io/pypi/v/noteable-origami">
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

---

[Install](#installation) | [Getting Started](#getting-started) | [Documentation](https://noteable-origami.readthedocs.io) | [License](./LICENSE) | [Code of Conduct](./CODE_OF_CONDUCT.md) | [Contributing](./CONTRIBUTING.md)

<!-- --8<-- [start:intro] -->

## Intro to Origami

Origami is a 🐍 Python library for talking to [Noteable notebooks](https://noteable.io/). This is the official way to access the full breadth of API calls and access patterns in async Python for rich programmatic access to notebooks. You can use [Noteable for free](https://app.noteable.io) with a quick signup.

<!-- --8<-- [end:intro] -->

<!-- --8<-- [start:requirements] -->

## Requirements

Python 3.8+

<!-- --8<-- [end:requirements] -->

<!-- --8<-- [start:install] -->

## Installation

### Poetry

```shell
poetry add noteable-origami
```

### Pip

```shell
pip install noteable-origami
```

<!-- --8<-- [end:install] -->

<!-- --8<-- [start:start] -->

## Getting Started

Get your API token from Noteable within user settings.
Within user settings, go to the API Token page, and generate a new token.

```python
from origami.client import NoteableClient

token = ''  # Your API token from Noteable

# Establish a connection to the realtime API
async with NoteableClient(api_token=token) as client:
    await client.ping_rtu()
```

### Token via Environment Variable

Alternatively you can set the environment variable:

```bash
NOTEABLE_TOKEN=xxxx
```

and skip assigning the token:

```python
async with NoteableClient() as client:
    await client.ping_rtu()
```

### Custom Domain

```bash
NOTEABLE_TOKEN=xxxx
NOTEABLE_DOMAIN=app.noteable.io
```

And the client will use that particular domain, for custom deployment location. This value defaults to `app.noteable.io`.

```python
async with NoteableClient() as client:
    await client.ping_rtu()
```

<!-- --8<-- [end:start] -->

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

---

<p align="center">Open sourced with ❤️ by <a href="https://noteable.io">Noteable</a> for the community.</p>

<img href="https://pages.noteable.io/private-beta-access" src="https://assets.noteable.io/github/2022-07-29/noteable.png" alt="Boost Data Collaboration with Notebooks">
