"""A utility file for helping with nbformat interface and conversions"""

import nbformat
import orjson
import structlog

logger = structlog.get_logger('noteable.' + __name__)


def ensure_notebook_latest_schema(nb: nbformat.NotebookNode) -> None:
    """Converts if needed a notebook to the v4 formatted JSON file schema"""
    if nb.get("nbformat", -1) < nbformat.v4.nbbase.nbformat:
        try:
            nbformat.convert(nb, to_version=nbformat.v4.nbbase.nbformat)
        except Exception:
            # Coerce any odd exceptions into validation errors so all these methods
            # are consistent in what they throw.
            logger.warn("Failed to convert notebook to latest schema", exc_info=True)
            raise nbformat.ValidationError("Failed to convert notebook to latest schema")

    nb.nbformat_minor = nbformat.v4.nbbase.nbformat_minor


def validate_against_latest_schema(notebook: nbformat.NotebookNode) -> None:
    """Confirms that the notebook is a v4 formatted JSON file"""
    try:
        nbformat.validate(
            notebook,
            version=nbformat.v4.nbbase.nbformat,
            version_minor=nbformat.v4.nbbase.nbformat_minor,
            repair_duplicate_cell_ids=True,
            strip_invalid_metadata=True,
        )
    except nbformat.ValidationError:
        logger.exception("Notebook JSON is invalid")
        raise
    except Exception:
        # This is warn-level because validate expects the notebook to roughly match the v4 schema
        # if you send a v3 notebook into this method it'll explode with a KeyError.
        logger.warn(
            "Hit some unexpected error validating a notebook against latest schema", exc_info=True
        )
        raise nbformat.ValidationError(
            "Hit some unexpected error validating a notebook against latest schema"
        )


def nbformat_fix_and_validate(notebook: nbformat.NotebookNode) -> None:
    """Takes a dictionary or notebooknode and does the following:

    1. Fixes common validation errors that are in our power to fix
    2. Does a validation run to ensure that the notebook document is valid for writing
    """
    ensure_notebook_latest_schema(notebook)
    validate_against_latest_schema(notebook)


def nbformat_writes_fast(notebook: nbformat.NotebookNode) -> bytes:
    """Uses orjson.dumps instead of json.dumps, without any indents.
    Still validates the incoming notebook with nbformat.validate.
    """
    nbformat_fix_and_validate(notebook)
    return orjson.dumps(notebook)


def isvalid(notebook: nbformat.NotebookNode) -> bool:
    """Validates a notebook without mutating its contents.
    Returns True if the notebook passed validation. False otherwise.

    `nbformat.isvalid` by default will mutate the notebook contents so we
    don't use that.
    """
    try:
        nbformat.validate(
            notebook,
            version=nbformat.v4.nbbase.nbformat,
            version_minor=nbformat.v4.nbbase.nbformat_minor,
            repair_duplicate_cell_ids=False,
            strip_invalid_metadata=False,
        )
        return True
    except nbformat.ValidationError:
        return False
