from datetime import datetime
from typing import Optional

import bitmath
from pydantic import BaseModel

from .files import NotebookFile, FileType


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
    execution_state: str = None
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
