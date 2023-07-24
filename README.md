# Origami

Origami is a Python SDK for the [Noteable](https://noteable.io/) platform. You can use it to create Notebooks, add code or markdown, and execute cells programmatically.

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


## API Tokens

The Noteable API requires an authentication token. You can manage tokens at the Noteable user settings page.

1. Log in to Noteable (sign up is free)
2. In the User Settings tab, navigate to `API Tokens` and generate a new token

## Usage

The example below shows how to create a Notebook, launch a Kernel, add new cells, and execute code. 

```python
# Grab a project_id from the Noteable UI, the url will look like: app.noteable.io/p/....
api_token = '...'
project_id = '...'

# Client for interacting with Noteables REST API
from origami.clients.api import APIClient
api_client = APIClient(api_token)

# Create a new Notebook
file = await api_client.create_notebook(project_id=project_id, path="Demo.ipynb")

# Start a Kernel
await api_client.launch_kernel(file.id)

# Client for Real-time Updates (RTU), used with Notebooks
rtu_client = await api_client.rtu_client(file.id)

# Add a new cell
from origami.models.notebook import CodeCell
cell = CodeCell(source="print('Hello World')")
await rtu_client.add_cell(cell)

# Execute the cell
queued_execution = await rtu_client.execute_cell(cell.id)

# Wait for the execution to be complete
cell = await queued_execution

# Grab the output
output_collection = await api_client.get_output_collection(cell.output_collection_id)
output_collection.outputs[0].content.raw
>>> 'Hello World\n'
```

## 1.0 Roadmap

Origami is heading towards a 1.0 release. The alpha release candidate is on Pypi now, installable with a `--pre` flag. The 1.0 release represents a major refactor of the Origami using the best practices and lessons learned from creating multiple production API and RTU clients, including our ChatGPT plugin. It will likely come out of alpha once all of our internal applications are using the Origami 1.0 syntax.