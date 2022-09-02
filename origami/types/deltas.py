"""Noteable FileDelta Models which represent incremental changes and actions against a file.
This is effectively a linear history log message format for a file over time.
"""

import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Generic, Optional, TypeVar

import structlog
from pydantic import BaseModel, root_validator, validator
from pydantic.generics import GenericModel

logger = structlog.get_logger(__name__)


class FileDeltaType(enum.Enum):
    """The type representation for the given file delta request indicating it's implied subclass"""

    def _generate_next_value_(name, start, count, last_values):
        """Helper to enable initialization / enumeration"""
        return name

    def __str__(self):
        """Helper to make printing pretty"""
        return self.value

    # nb_metadata actions: add, update, delete
    nb_metadata = enum.auto()
    # nb_cells actions: insert, replace, delete, delete_many, move, move_many
    nb_cells = enum.auto()
    # cell_metadata actions: add, replace, delete
    cell_metadata = enum.auto()
    # cell_contents actions: insert, delete, replace, move
    cell_contents = enum.auto()
    # cell_outputs actions: append, clear
    cell_outputs = enum.auto()
    # cell_output_collection actions: replace
    cell_output_collection = enum.auto()
    # cell_output_collection actions: replace
    nb_output_collection = enum.auto()
    # cell_execute actions: execute, execute_all, execute_before, execute_after
    cell_execute = enum.auto()


class FileDeltaAction(enum.Enum):
    """The type representation for the given action of a file delta represents"""

    def _generate_next_value_(name, start, count, last_values):
        """Helper to enable initialization / enumeration"""
        return name

    def __str__(self):
        """Helper to make printing pretty"""
        return self.value

    add = enum.auto()
    update = enum.auto()
    delete = enum.auto()
    insert = enum.auto()
    replace = enum.auto()
    delete_many = enum.auto()
    move = enum.auto()
    move_many = enum.auto()
    append = enum.auto()
    clear = enum.auto()
    execute = enum.auto()
    execute_all = enum.auto()
    execute_before = enum.auto()
    execute_after = enum.auto()


# A sentinel value for deltas that aren't associated with any resource
# right now. Using this too liberally could mean lots of conflicts as
# we enforce the unique constraint on (delta_type, resource_id, parent_delta_id).
NULL_RESOURCE_SENTINEL = "__NULL_RESOURCE__"

NULL_PARENT_DELTA_SENTINEL = uuid.UUID(int=0)

NULL_PRIOR_VALUE_SENTINEL = "__NULL_PRIOR_VALUE__"


@enum.unique
class CellState(enum.Enum):
    """The type representation for cell state within a cell status message."""

    def _generate_next_value_(name, start, count, last_values):
        """Helper for generator enumeration"""
        return name

    not_run = enum.auto()
    queued = enum.auto()
    executing = enum.auto()
    finished_with_no_error = enum.auto()
    finished_with_error = enum.auto()
    catastrophic_failure = enum.auto()
    dequeued = enum.auto()  # example: was queued, but interrupted before it could run.
    # Temporarily deprecated - we may start using this again when we can positively observe interruption (e.g., by
    # inspecting kernel messages for a KeyboardInterrupt)
    interrupted = enum.auto()  # example: was running, but interrupted before it could finish.

    @property
    def is_terminal_state(self):
        """The state of a cell post-execution."""
        return self in {
            CellState.not_run,
            CellState.finished_with_no_error,
            CellState.finished_with_error,
            CellState.catastrophic_failure,
            CellState.dequeued,
            CellState.interrupted,
        }

    @property
    def is_error_state(self):
        """The states in which an unexpected event has occurred during or before execution"""
        return self in {
            CellState.finished_with_error,
            CellState.catastrophic_failure,
            CellState.dequeued,
            CellState.interrupted,
        }


class CellStateMessage(BaseModel):
    """The message format used to indicate cell status changes as execution progresses."""

    kernel_session_id: uuid.UUID
    cell_id: str
    state: CellState
    execution_count: Optional[int]

    # This is the server's time at which it recieved an execution request
    queued_at: Optional[datetime]
    # Start and finish times are taken from planar-ally messages (set from kernel's time of witnessing)
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    duration_secs: Optional[float]

    queued_by_id: Optional[uuid.UUID]  # user ID


class V2CellMetadataProperties(BaseModel):
    """The properties field subtypes for cell metadata delta events"""

    path: Optional[list]
    value: Any

    # Optional field for clients to specify what the previous value was before firing this off.
    # This is primarily useful for ensuring that metadata updates are idempotent, which can be
    # important if several events are fired at once that would update the same value.
    prior_value: Any = NULL_PRIOR_VALUE_SENTINEL

    # These got collapsed into a single schema because they both use the same
    # delta_action/type combination and there's no way to figure out which one
    # the user meant without inspecting the old-style RTU message event.
    # In the future we may want to split these out into separate delta types
    # so that it's super-clear what should be happening at any given time.
    language: Optional[str]
    type: Optional[str]

    @validator("path")
    def validate_path(cls, path, values):
        """Originally we supported strings here but AFAIK they weren't used."""
        if isinstance(path, str):
            return [path]
        return path


class V2CellContentsProperties(BaseModel):
    """The properties field subtypes for contents delta events"""

    patch: Optional[str]
    source: Optional[str]


class NBCellProperties(BaseModel):
    """The properties field subtypes for cell action delta events"""

    id: str
    after_id: Optional[str] = None  # null if first cell
    # There some conflation here between cell attributes, cell metadata,
    # and things like the ordering of the cell in a notebook + its id.
    # We could probably do better and provide some extra delta types to
    # make this more clear.
    cell: Optional[dict]


class NBMetadataProperties(BaseModel):
    """The properties field subtypes for notebook metadata delta events"""

    path: list
    value: Any
    prior_value: Any


class V2CellOutputCollectionProperties(BaseModel):
    """This delta type is just a subset of cell metadata updates
    so when we formalize the spec here we should consider collapsing these
    for simplicity.
    """

    output_collection_id: uuid.UUID


DeltaPropertiesT = TypeVar("DeltaPropertiesT")


class FileDeltaRequestBase(GenericModel, Generic[DeltaPropertiesT]):
    """The base type model for FileDelta requests being egnerated. This is used
    to provide specializations for particular message types without needing to
    specify these common fields.
    """

    id: uuid.UUID
    delta_type: FileDeltaType
    delta_action: FileDeltaAction
    resource_id: str = NULL_RESOURCE_SENTINEL
    parent_delta_id: Optional[uuid.UUID]

    # Properties for rendering the specified file delta.
    # They may differ for each delta_type and action.
    properties: Optional[DeltaPropertiesT]

    class Config:
        """Indicates we allow enum values in the dataclass"""

        use_enum_values = True


class FileDeltaBase(FileDeltaRequestBase[DeltaPropertiesT], Generic[DeltaPropertiesT]):
    """The base type model for FileDeltas reponses. This is used to provide specializations
    for particular message types without needing to specify these common fields.
    """

    file_id: uuid.UUID
    created_by_id: Optional[uuid.UUID]

    class Config:
        """Indicates we allow enum values in the dataclass"""

        use_enum_values = True


class FileDelta(FileDeltaBase[Dict]):
    """A generic type wrapper for any history event request/replies that track
    real time updates against a file.
    """

    # optional since it isn't specified when creating a file delta, but is returned
    created_at: Optional[datetime]

    def validate_data(self):
        """Coerces the `properties` type and runs validation against it.

        Will raise a ValidationError if we fail validation against the new model
        """
        try:
            delta_type = FileDeltaType(self.delta_type)
        except ValueError:
            delta_type = None

        if delta_type is FileDeltaType.cell_metadata:
            return CellMetadataDelta.parse_obj(self)
        elif delta_type is FileDeltaType.cell_contents:
            return CellContentsDelta.parse_obj(self)
        elif delta_type is FileDeltaType.nb_cells:
            return NBCellDelta.parse_obj(self)
        elif delta_type is FileDeltaType.nb_metadata:
            return NBMetadataDelta.parse_obj(self)
        elif delta_type is FileDeltaType.cell_output_collection:
            return CellOutputCollectionDelta.parse_obj(self)
        elif delta_type is FileDeltaType.cell_execute:
            return CellExecuteDelta.parse_obj(self)

        logger.warn("Delta type without data validation", delta_type=str(self.delta_type))
        return self


CellMetadataDelta = FileDeltaBase[V2CellMetadataProperties]
NBCellDelta = FileDeltaBase[NBCellProperties]
NBMetadataDelta = FileDeltaBase[NBMetadataProperties]
CellExecuteDelta = FileDeltaBase[Any]
CellOutputCollectionDelta = FileDeltaBase[V2CellOutputCollectionProperties]
CellContentsDelta = FileDeltaBase[V2CellContentsProperties]


class CellContentsDeltaRequestData(FileDeltaRequestBase[V2CellContentsProperties]):
    """The type representing a content change in a document"""

    @root_validator
    def validate_properties(cls, values):
        """Validates that we have a proper cell content payload with at least one optional value."""
        delta_action, properties = (
            FileDeltaAction(values.get("delta_action")),
            values.get("properties"),
        )

        if properties:
            assert not all(
                [
                    properties.patch is not None,
                    properties.source is not None,
                ]
            ), "properties must either contain patch or source, not both"
        assert any(
            [
                delta_action
                in (
                    FileDeltaAction.execute,
                    FileDeltaAction.execute_all,
                    FileDeltaAction.execute_before,
                    FileDeltaAction.execute_after,
                )
                and properties is None,  # noqa: W503
                delta_action == FileDeltaAction.replace and properties.source is not None,
                delta_action == FileDeltaAction.update and properties.patch is not None,
            ]
        ), f"invalid properties for delta_action {delta_action} with properties: {properties}"
        return values


class CellContentsDeltaRequestDataWrapper(BaseModel):
    """Wrapper for delta contents which is always inside a 'delta' key"""

    delta: CellContentsDeltaRequestData


class FileDeltaRequest(BaseModel):
    id: uuid.UUID
    parent_delta_id: Optional[uuid.UUID]
    delta_type: FileDeltaType
    delta_action: FileDeltaAction
    resource_id: str = NULL_RESOURCE_SENTINEL
    properties: Optional[Dict]

    def to_delta(self, file_id: uuid.UUID, created_by_id: uuid.UUID):
        obj = self.dict()
        obj["file_id"] = file_id
        obj["created_by_id"] = created_by_id
        delta = FileDelta.construct(**obj)
        return delta.validate_data()


class NewFileDeltaData(BaseModel):
    delta: FileDeltaRequest
    output_collection_id_to_copy: Optional[uuid.UUID] = None
