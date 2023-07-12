from typing import Annotated, Union

from pydantic import Field

from origami.models.rtu.base import BaseRTUResponse
from origami.models.rtu.channels.files import FileRequests, FileResponses
from origami.models.rtu.channels.kernels import KernelRequests, KernelResponses
from origami.models.rtu.channels.system import SystemRequests, SystemResponses
from origami.models.rtu.errors import RTUError

# Use: pydantic.pares_obj_as(RTURequest, <payload-as-dict>)
RTURequest = Annotated[
    Union[
        FileRequests,
        KernelRequests,
        SystemRequests,
    ],
    Field(discriminator='channel_prefix'),
]

# Use: pydantic.pares_obj_as(RTUResponse, <payload-as-dict>)
# If the payload isn't a normal response by channel/event, will fall back to trying to parse as an
# RTUError (invalid event, invalid data, permission denied) or error out entirely. If it's not an
# error or known model, parse as base response. RTU Client will log a warning for base responses.
RTUResponse = Union[
    Annotated[
        Union[
            FileResponses,
            KernelResponses,
            SystemResponses,
        ],
        Field(discriminator='channel_prefix'),
    ],
    RTUError,
    BaseRTUResponse,
]
