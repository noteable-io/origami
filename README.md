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

For stable release:

```bash
pip install noteable-origami
```

```bash
poetry add noteable-origami
```

For alpha pre-release:

```bash
pip install noteable-origami --pre
```

<!-- --8<-- [end:install] -->

<!-- --8<-- [start:start] -->

## Getting Started

> **Warning**
> Developer note: this documentation is written for the 1.0 alpha release. For stable release, see [pre-1.0 README](https://github.com/noteable-io/origami/blob/release/0.0.35/README.md)

### API Tokens

The Noteable API requires an authentication token. You can manage tokens at the Noteable user settings page.

1. Log in to Noteable (sign up is free)
2. In the User Settings tab, navigate to `API Tokens` and generate a new token

### Usage

The example below shows how to create a Notebook, launch a Kernel, add new cells, and execute code.

```python
# Get your API token from the User Settings page by clicking your account name in the upper right
api_token = os.environ['NOTEABLE_TOKEN']

# Client for interacting with Noteables REST API
from origami.clients.api import APIClient
api_client = APIClient(api_token)

# Sanity check your user information
user = await api_client.user_info()

# Choose a project to create the notebook in, here using the ChatGPT plugin default project
project_id = user.origamist_default_project_id

# Create a new Notebook
file = await api_client.create_notebook(project_id=project_id, path="Demo.ipynb")

# Start a Kernel
await api_client.launch_kernel(file.id)

# Client for Real-time Updates (RTU), used with Notebooks
realtime_notebook = await api_client.connect_realtime(file)

# Add a new cell
from origami.models.notebook import CodeCell
cell = CodeCell(source="print('Hello World')")
await realtime_notebook.add_cell(cell)

# Execute the cell. The returned value is a dictionary of Futures. Awaiting those futures will
# block until the cells have completed execution
queued_execution = await realtime_notebook.queue_execution(cell.id)

# The return value of the Futures is the up-to-date cell. If there's output, an output collection id
# will be set on the cell metadata
cells = await asyncio.gather(*queued_execution)

# Grab the output
cell = cells[0]
output_collection = await api_client.get_output_collection(cell.output_collection_id)
print(output_collection.outputs[0].content.raw) # 'Hello World\n'
```

<!-- --8<-- [end:start] -->

## 1.0 Roadmap

Origami 1.0 implies that we have a stable architecture such as a split of `APIClient` and `RTUClient` and the layout of the RTU modeling. Some syntax may change as Origami is integrated into production components. Any breaking changes will be a minor version bump.

## CLI

Origami has a small CLI for fetching the content of a Notebook, and tailing a Notebook to see all RTU messages being emitted on the relevant RTU channels.

```
pip install noteable-origami[cli]
poetry install -E cli
```

1. Fetch the content of a Notebook and write to file: `origami fetch <file-id> notebook.ipynb`
2. Tail a Notebook, useful when debugging RTU messages: `origami tail <file-id>`


## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md).

---

<p align="center">Open sourced with ❤️ by <a href="https://noteable.io">Noteable</a> for the community.</p>

<img href="https://pages.noteable.io/private-beta-access" src="https://assets.noteable.io/github/2022-07-29/noteable.png" alt="Boost Data Collaboration with Notebooks">
