To rebuild the site run:

```bash
PYTHONPATH=path/to/origami/origami mkdocs build
```

To serve the docs run:

```bash
PYTHONPATH=path/to/origami/origami mkdocs serve
```

To verify a file has appropriate commenting to support mkdocs use:

```bash
python -m doctest origami/path/to/file.py
```

No output means the file has been fully commented and accepted.
