import enum
import uuid
from typing import Optional

from pydantic import BaseModel, root_validator


class JobInstanceAttemptStatus(str, enum.Enum):
    """The status of a job instance attempt.

    A successful attempt will have the following status changes: CREATED -> RUNNING -> SUCCEEDED
    A failed attempt will have the following status changes: CREATED -> RUNNING -> FAILED
    """

    def _generate_next_value_(name: str, *args, **kwargs) -> str:
        return name

    CREATED = enum.auto()  # created but not yet started
    RUNNING = enum.auto()  # started but not yet completed
    SUCCEEDED = enum.auto()  # completed successfully
    FAILED = enum.auto()  # completed unsuccessfully

    def __str__(self):
        return self.value


class JobInstanceAttempt(BaseModel):
    status: JobInstanceAttemptStatus
    attempt_number: int

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
    `noteable_job_instance_id` and `customer_job_definition_reference_id` may be optionally supplied;
     they will associate the parameterized notebook with a job instance and job definition.
    """

    notebook_version_id: Optional[uuid.UUID]
    job_instance_attempt: Optional[JobInstanceAttempt]
