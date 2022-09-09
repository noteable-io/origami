"""This file captures everything Kernel related in regards to model and helper functions."""

import enum
import uuid
from datetime import datetime
from typing import Optional

import bitmath
from pydantic import BaseModel

from .files import NotebookFile


@enum.unique
class KernelStatus(enum.Enum):
    """The kernel status enumeration which captures all states that a kernel can land in.

    This class also provides some helpers for checking if certain actions or responses
    are available based on the current state.
    """

    # The kernel has been requested in kubernetes and is being scheduled on an
    # available node. If it's unable to be scheduled then the status will never
    # go to scheduled.
    REQUESTED = "requested"

    # This Gate instance knows about the kernel and is waiting to request resources
    # from Kubernetes.
    SCHEDULED = "scheduled"

    # In the case of a new node, the docker images will need to be pulled and
    # this state may last longer in those cases.
    PULLING_INIT_RESOURCES = "pulling-initialization-resources"
    # Kernel initialization happens immediately after the docker images are pulled,
    # this step includes pulling project files. The state may cycle between this and
    # pulling-initialization-resources if there are multiple init containers.
    INIT_CONTAINER_STARTED = "init-container-started"

    # After init containers are run, kubernetes will pull docker images for the kernel container and planar-ally.
    PULLING_RUNTIME_RESOURCES = "pulling-runtime-resources"
    # After a runtime container's resources are pulled the container will be started,
    # this state may be sent more than once and cycle between this state and pulling-runtime-resources.
    RUNTIME_CONTAINER_STARTED = "runtime-container-started"

    # The kernel container and planar-ally are starting up but not ready to accept ZMQ connections/requests
    PREPARING = "preparing"

    # After all the kernel containers are created, the launching state is emitted to show that the
    # containers are now starting up but are not ready to accept connections.
    LAUNCHING = "launching"

    # Kernel has accepted a ZMQ connection. Sent by the server to indicate that
    # a kernel is ready for input even if it hasn't sent a status message.
    LAUNCHED = "launched"

    # Kernel has been successfully bootstrapped and we're waiting on the kernel to
    # accept ZMQ connections. This is sent by the kernel while it's preparing its
    # environment.
    STARTING = "starting"

    # Kernel is ready for input.
    IDLE = "idle"

    # Kernel is processing input.
    BUSY = "busy"

    # Kernel has been shutdown and we're waiting on it to restart. Sent by the server
    # to indicate that this process has begun.
    RESTARTING = "restarting"

    # Sent by planar-ally when the kernel restarted because it failed a liveness check,
    # this is commonly sent when the kernel OOMs.
    FORCED_RESTART = "forced-restart"

    # Kernel shutdown has been initiated and is being awaited. Sent
    # server to indicate that a kernel shutdown request is pending.
    SHUTTING_DOWN = "shutting down"

    # Kernel has been shutdown and we're not expecting it to restart. Sent by the
    # server to indicate that a kernel shutdown request was fulfilled.
    SHUTDOWN = "shutdown"

    # Kernel has been shutdown by an outside process. Sent by the server when it
    # attempts to refresh connection data and discovers that the kernel pod no
    # longer exists. Or by the kernel sidecar when a kernel has been idle too long.
    CULLED = "culled"

    # Kernel failed to bootstrap. Sent by the server when we fail to process a kernel
    # start request.
    FAILED = "failed"

    def __str__(self):
        """Helper for serialization"""
        return self.value

    @property
    def kernel_is_in_valid_state(self):
        """Returns whether the state is valid to be used and executed against."""
        return self not in {
            KernelStatus.FAILED,
            KernelStatus.CULLED,
            KernelStatus.RESTARTING,
            KernelStatus.FORCED_RESTART,
        }

    @classmethod
    def not_live_statuses(cls):
        """Statuses of kernel session rows that don't count against a user's current active session count"""
        return {
            KernelStatus.FAILED,
            KernelStatus.CULLED,
            KernelStatus.SHUTDOWN,
            KernelStatus.SHUTTING_DOWN,
        }

    @property
    def kernel_is_gone(self):
        """Returns a boolean about whether the kernel shouldn't be expected to
        transition or be in live stat that can take requests without a launch request.
        """
        return self in self.not_live_statuses()

    @property
    def kernel_is_alive(self):
        """Returns a boolean about whether the kernel should be expected to
        respond to requests.

        Mostly used so we don't accidentally mark a kernel manager as "culled"
        when it's still coming up.
        """
        return self in {
            KernelStatus.LAUNCHED,
            KernelStatus.STARTING,
            KernelStatus.IDLE,
            KernelStatus.BUSY,
        }

    @property
    def include_system_utilization(self) -> bool:
        """Statuses that also include system resource stats when sent"""
        return self in {KernelStatus.IDLE, KernelStatus.BUSY}

    @property
    def include_container_info(self) -> bool:
        """Indicates states that have container information rather than kernel specific fields"""
        return self in {
            KernelStatus.PULLING_INIT_RESOURCES,
            KernelStatus.PULLING_RUNTIME_RESOURCES,
            KernelStatus.INIT_CONTAINER_STARTED,
            KernelStatus.RUNTIME_CONTAINER_STARTED,
        }


class NotebookDetails(BaseModel):
    """Details found in the notebook section of session responses"""

    name: str = ''  # Unused in source - always set to '' in jupyter land
    path: str


class APIBitmathField(str):
    """A model representation used to populate a hardware size string that serializes nicely"""

    @classmethod
    def __get_validators__(cls):
        """Overwrite validator fetch to use our method(s)"""
        yield cls.validate

    @classmethod
    def __modify_schema__(cls, field_schema):
        """Helper for docstrings"""
        field_schema.update(examples=["2GB", "16GiB"])

    @classmethod
    def validate(cls, v):
        """Confirm we have a bit-size patterned string"""
        if isinstance(v, bitmath.Bitmath):
            return str(v)
        if not isinstance(v, str):
            raise TypeError("string required for APIBitmathField")
        return v


class APIHardwareSize(BaseModel):
    """This model should be used when exposing a HardwareSize via API to the frontend"""

    identifier: str
    display_name: str

    memory_limit: APIBitmathField
    cpu_limit: float


class KernelMetadata(BaseModel):
    """Wraps any request metadata options available to session kernel calls"""

    # The identifier of the HardwareSize, if not specified, the default will be used
    hardware_size: Optional[APIHardwareSize] = None


class KernelRequestMetadata(BaseModel):
    """Wraps any request metadata options available to sessions calls"""

    # The identifier of the HardwareSize, if not specified, the default will be used
    hardware_size_identifier: Optional[str] = None


class KernelDetails(BaseModel):
    """Represents information about the kernel and its state"""

    # TODO: Cleanup unused fields when this moves to next API verison / RTU
    name: str
    id: Optional[str]
    last_activity: datetime = None
    execution_state: Optional[KernelStatus] = None
    connections: int = 0  # Unused at noteable
    metadata: Optional[KernelMetadata] = None

    @property
    def hardware_size_identifier(self) -> Optional[str]:
        """Helper to pull out the hardware identifier from response metadata"""
        if self.metadata:
            return self.metadata.hardware_size_identifier
        return None


class KernelRequestDetails(BaseModel):
    """Encapsulates the kernel details available in a kernel session request."""

    name: str
    metadata: Optional[KernelRequestMetadata] = None


class StartKernelSession(BaseModel):
    """The kernel name and optional hardware size to use at the start of a Kernel session."""

    kernel_name: str
    hardware_size_identifier: Optional[str]


class SessionRequestDetails(BaseModel):
    """Represents a SessionRequest form that asks about a notebook / kernel session."""

    file_id: uuid.UUID
    kernel_config: StartKernelSession

    @classmethod
    def generate_file_request(
        cls,
        file: NotebookFile,
        kernel_name: Optional[str] = None,
        hardware_size: Optional[str] = None,
    ) -> 'SessionRequestDetails':
        """Generates a session request for a given file as a helper method.

        The function sets the hardware size and kernel info from the file and
        places it in the corresponding request fields.
        """
        metadata = file.json_contents['metadata']
        kernel_name = kernel_name or metadata.get('kernel_info', {}).get('name', 'python3')
        hardware_size = hardware_size or metadata.get('selected_hardware_size')
        return SessionRequestDetails(
            file_id=file.id,
            kernel_config=StartKernelSession(
                kernel_name=kernel_name, hardware_size_identifier=hardware_size
            ),
        )
