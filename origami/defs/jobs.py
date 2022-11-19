import enum
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, root_validator

from .files import NotebookFile
from .models import NoteableAPIModel

_last_triggered_by_doc = "Any string that can be used to identify the last user to trigger the job in the orchestration system."  # noqa: E501
_orchestrator_id_doc = "Any string used to uniquely identify the orchestration system."
_orchestrator_name_doc = "Any string used to reference the orchestration system name."
_orchestrator_uri_doc = "A URI to access the orchestration system."
_orchestrator_job_definition_id_doc = (
    "Any string used to uniquely identify the job definition in the orchestration system."
)
_orchestrator_job_definition_uri_doc = (
    "A URI to access the job definition in the orchestration system."
)


class CustomerJobDefinitionReferenceInput(BaseModel):
    """Input to create a new customer job definition reference."""

    space_id: uuid.UUID
    orchestrator_id: Optional[str] = Field(description=_orchestrator_id_doc)
    orchestrator_uri: Optional[str] = Field(description=_orchestrator_uri_doc)
    orchestrator_name: Optional[str] = Field(description=_orchestrator_name_doc)
    orchestrator_job_definition_id: Optional[str] = Field(
        description=_orchestrator_job_definition_id_doc
    )
    orchestrator_job_definition_uri: Optional[str] = Field(
        description=_orchestrator_job_definition_uri_doc
    )


class CustomerJobDefinitionReference(NoteableAPIModel):
    """A reference to a customer job definition in an orchestration system."""

    space_id: uuid.UUID
    orchestrator_id: Optional[str] = Field(description=_orchestrator_id_doc)
    orchestrator_uri: Optional[str] = Field(description=_orchestrator_uri_doc)
    orchestrator_name: Optional[str] = Field(description=_orchestrator_name_doc)
    orchestrator_job_definition_id: Optional[str] = Field(
        description=_orchestrator_job_definition_id_doc
    )
    orchestrator_job_definition_uri: Optional[str] = Field(
        description=_orchestrator_job_definition_uri_doc
    )

    created_by_id: Optional[uuid.UUID]

    class Config:
        orm_mode = True


class CustomerJobInstanceReferenceInput(BaseModel):
    """Create a new job instance reference.

    This will also be used to create or update a job definition reference.
    `customer_job_definition_reference_id` can be used to explicitly specify which job definition reference to update.
    If not set, the job definition reference will be updated based on the `orchestrator_id` and `orchestrator_job_definition_id`.

    When specified, the URI fields will be shown in the UI to allow the user to access the job instance or job definition in the orchestration tool.  # noqa: E501
    """

    # job instance fields
    orchestrator_job_instance_id: Optional[str]
    orchestrator_job_instance_uri: Optional[str]
    last_triggered_by_id: Optional[str] = Field(description=_last_triggered_by_doc)

    # job definition fields
    customer_job_definition_reference_id: Optional[uuid.UUID]
    customer_job_definition_reference: Optional[CustomerJobDefinitionReferenceInput]

    @root_validator(pre=True)
    def validate_customer_job_definition_reference(cls, values):
        reference = values.get("customer_job_definition_reference")
        reference_id = values.get("customer_job_definition_reference_id")
        if not (reference or reference_id):
            raise ValueError(
                "Either customer_job_definition_reference or customer_job_definition_reference_id must be specified."
            )
        return values


class CustomerJobInstanceReference(NoteableAPIModel):
    """A reference to a job instance in an orchestration system.

    This can generally be thought of as an instance of a job definition.
    """

    customer_job_definition_reference_id: uuid.UUID
    orchestrator_job_instance_id: Optional[str]
    orchestrator_job_instance_uri: Optional[str]
    last_triggered_by_id: Optional[str] = Field(description=_last_triggered_by_doc)
    last_run_at: Optional[datetime] = Field(
        description="The last time the job instance was run. None if the job instance has not been run yet."
    )
    last_success_at: Optional[datetime] = Field(
        description="The last time the job instance was run successfully. "
        "None if the job instance has not been successfully run yet."
    )

    class Config:
        orm_mode = True


class JobInstanceAttemptStatus(str, enum.Enum):
    """The status of a job instance attempt.

    A successful attempt will have the following status changes: CREATED -> RUNNING -> SUCCEEDED
    A failed attempt will have the following status changes: CREATED -> RUNNING -> FAILED
    """

    def _generate_next_value_(name: str, *args, **kwargs) -> str:
        return name

    CREATED = enum.auto()  # created but execution has not yet started
    RUNNING = enum.auto()  # execution started but not yet completed
    SUCCEEDED = enum.auto()  # completed successfully
    FAILED = enum.auto()  # completed unsuccessfully

    def __str__(self):
        return self.value


class JobInstanceAttemptRequest(BaseModel):
    """
    Represents an attempt to execute a job.

    A job attempt holds the execution status of an attempt and the ordinal number of the attempt.
    Optionally, a job instance id can be set for a job attempt.
    """

    status: JobInstanceAttemptStatus = Field(default=JobInstanceAttemptStatus.CREATED)
    attempt_number: int = Field(default=0)

    # A parameterized notebook may be associated with a job instance, but is not required to.
    # If exactly one of these are set, then a JobInstanceAttempt will be created for the parameterized notebook.
    noteable_job_instance_id: Optional[uuid.UUID]
    customer_job_instance_reference_id: Optional[uuid.UUID]

    @root_validator(pre=True)
    def validate_job_instance_ids(cls, values):
        noteable_job_instance_id = values.get("noteable_job_instance_id")
        customer_job_instance_reference_id = values.get("customer_job_instance_reference_id")
        if noteable_job_instance_id and customer_job_instance_reference_id:
            raise ValueError(
                "Exactly one of `noteable_job_instance_id` and `customer_job_instance_reference_id` must be set."
            )
        return values


class CreateParameterizedNotebookRequest(BaseModel):
    """
    A request to create a new parameterized notebook for parameterized execution.

    `noteable_job_instance_id` and `customer_job_definition_reference_id` may be optionally supplied;
     they will associate the parameterized notebook with a job instance and job definition.
    """

    notebook_version_id: Optional[uuid.UUID]
    job_instance_attempt: Optional[JobInstanceAttemptRequest]


class JobInstanceAttempt(NoteableAPIModel):
    """Represents a job instance attempt returned by the Noteable API."""

    noteable_job_instance_id: Optional[uuid.UUID]
    customer_job_instance_reference_id: Optional[uuid.UUID]
    status: JobInstanceAttemptStatus
    attempt_number: int
    parameterized_notebook_id: uuid.UUID

    class Config:
        orm_mode = True


class CreateParameterizedNotebookResponse(BaseModel):
    """The response to a request to create a parameterized notebook.

    Return the created job instance attempt here to provide the id to the client for any further job instance attempt
    status updates.
    """

    parameterized_notebook: NotebookFile
    job_instance_attempt: Optional[JobInstanceAttempt] = Field(
        description="The job instance attempt associated with the parameterized notebook."
    )


class JobInstanceAttemptUpdate(BaseModel):
    status: JobInstanceAttemptStatus = Field(description="The status of the job instance attempt.")
