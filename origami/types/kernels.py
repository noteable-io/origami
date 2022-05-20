import enum
from datetime import datetime
from typing import Optional

import bitmath
from pydantic import BaseModel

from .files import NotebookFile, FileType


@enum.unique
class KernelStatus(enum.Enum):
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

    @property
    def is_noteable_message(self):
        return self not in {KernelStatus.IDLE, KernelStatus.BUSY}

    @classmethod
    def not_live_statuses(cls):
        """
        Statuses of kernel session rows that don't count against a user's current active session count.
        """
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
    def kernel_is_ready(self):
        """Returns true if the kernel is ready to accept requests."""
        return self == KernelStatus.IDLE

    @property
    def include_system_utilization(self) -> bool:
        return self in {KernelStatus.IDLE, KernelStatus.BUSY}

    @property
    def include_container_info(self) -> bool:
        return self in {
            KernelStatus.PULLING_INIT_RESOURCES,
            KernelStatus.PULLING_RUNTIME_RESOURCES,
            KernelStatus.INIT_CONTAINER_STARTED,
            KernelStatus.RUNTIME_CONTAINER_STARTED,
        }

    @property
    def needs_info_request(self) -> bool:
        return self in {KernelStatus.STARTING, KernelStatus.FORCED_RESTART}


class NotebookDetails(BaseModel):
    name: str = ''  # Unused in source - always set to '' in jupyter land
    path: str


class APIBitmathField(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(examples=["2GB", "16GiB"])

    @classmethod
    def validate(cls, v):
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
    # The identifier of the HardwareSize, if not specified, the default will be used
    hardware_size: Optional[APIHardwareSize] = None


class KernelRequestMetadata(BaseModel):
    # The identifier of the HardwareSize, if not specified, the default will be used
    hardware_size_identifier: Optional[str] = None


class KernelDetails(BaseModel):
    """Represents information about the kernel and its state"""

    name: str
    id: Optional[str]
    last_activity: datetime = None
    execution_state: Optional[KernelStatus] = None
    connections: int = 0  # Unused at noteable
    metadata: Optional[KernelMetadata] = None

    @property
    def hardware_size_identifier(self) -> Optional[str]:
        if self.metadata:
            return self.metadata.hardware_size_identifier
        return None

class KernelRequestDetails(BaseModel):
    name:str
    id: Optional[str]
    metadata: Optional[KernelRequestMetadata] = None


class SessionDetails(BaseModel):
    id: str = None
    name: str = ''  # Also unused in source - always set to '' in jupyter land
    path: str
    type: FileType = FileType.notebook  # Unused in source? Nteract only ever sends "notebook", too
    kernel: KernelDetails
    notebook: NotebookDetails = None


class SessionRequestDetails(BaseModel):
    name: str = ''  # Also unused in source - always set to '' in jupyter land
    path: str
    type: FileType = FileType.notebook  # Unused in source? Nteract only ever sends "notebook", too
    kernel: KernelRequestDetails

    @classmethod
    def generate_file_request(cls, file: NotebookFile, kernel_name: Optional[str]=None, hardware_size: Optional[str]=None) -> 'SessionRequestDetails':
        metadata = file.json_contents['metadata']
        kernel_name = kernel_name or metadata.get('kernel_info', {}).get('name', 'python3')
        hardware_size = hardware_size or metadata.get('selected_hardware_size')
        request_metadata = KernelRequestMetadata(hardware_size_identifier=hardware_size) if hardware_size else None
        return SessionRequestDetails(path=f'{file.project_id}/{file.filename}', type='notebook', kernel=KernelRequestDetails(
            name=kernel_name, metadata=request_metadata
        ))
