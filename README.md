# Origami
A library capturing message patterns and protocols speaking to Noteable's APIs
<p align="center">
<a href="https://github.com/noteable-io/origami/actions/workflows/ci.yaml">
    <img src="https://github.com/noteable-io/origami/actions/workflows/ci.yaml/badge.svg" alt="CI" />
</a>
<a href="https://codecov.io/gh/noteable-io/origami" > 
 <img src="https://codecov.io/gh/noteable-io/origami/branch/main/graph/badge.svg" alt="codecov code coverage"/> 
 </a>
<img alt="PyPI - License" src="https://img.shields.io/pypi/l/noteable-origami" />
<img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/noteable-origami" />
<img alt="PyPI" src="https://img.shields.io/pypi/v/magicbell">
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
</p>

---------

[Install](#installation) | [Getting Started](#getting-started) | [License](./LICENSE) | [Code of Conduct](./CODE_OF_CONDUCT.md) | [Contributing](./CONTRIBUTING.md)

## Requirements

Python 3.8+

## Installation

### Poetry

```shell
poetry add noteable-origami
```


### Pip
```shell
pip install noteable-origami
```

## Getting Started

Get your access token from https://app.noteable.world/api/token

```python
from origami.client import NoteableClient

token = 'ey...' # from https://app.noteable.world/api/token
async with NoteableClient(api_token=token) as client:
    await client.ping_rtu()
```

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

-------

<p align="center">Open sourced with ❤️ by <a href="https://noteable.io">Noteable</a> for the community.</p>

<img href="https://pages.noteable.io/private-beta-access" src="https://assets.noteable.io/github/2022-07-29/noteable.png" alt="Boost Data Collaboration with Notebooks">
