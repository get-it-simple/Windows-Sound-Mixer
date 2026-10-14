from dataclasses import dataclass

from pycaw.constants import DEVICE_STATE, EDataFlow, ERole
from pycaw.pycaw import AudioUtilities


@dataclass(frozen=True)
class OutputDevice:
    id: str
    name: str


def read_output_devices() -> tuple[list[OutputDevice], str]:
    devices = AudioUtilities.GetAllDevices(
        data_flow=EDataFlow.eRender.value, device_state=DEVICE_STATE.ACTIVE.value
    )
    outputs = [OutputDevice(device.id, device.FriendlyName or device.id) for device in devices]
    try:
        default = AudioUtilities.GetSpeakers()
        current_id = default.id if default is not None else ""
    except Exception:
        current_id = ""
    return outputs, current_id


def select_output_device(device_id: str) -> None:
    AudioUtilities.SetDefaultDevice(device_id, roles=[ERole.eConsole, ERole.eMultimedia])
