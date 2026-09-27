import ctypes
import logging
import sys
from ctypes import wintypes


logger = logging.getLogger(__name__)

IDLE_PRIORITY_CLASS = 0x00000040
PROCESS_POWER_THROTTLING_CURRENT_VERSION = 1
PROCESS_POWER_THROTTLING_EXECUTION_SPEED = 0x1
PROCESS_POWER_THROTTLING = 4


class ProcessPowerThrottlingState(ctypes.Structure):
    _fields_ = [
        ("Version", wintypes.ULONG),
        ("ControlMask", wintypes.ULONG),
        ("StateMask", wintypes.ULONG),
    ]


def _last_error(kernel32) -> int:
    try:
        return int(kernel32.GetLastError())
    except (AttributeError, OSError, TypeError, ValueError):
        return 0


def enable_efficiency_mode() -> bool:
    if sys.platform != "win32":
        return False

    try:
        kernel32 = ctypes.windll.kernel32
        get_current_process = kernel32.GetCurrentProcess
        get_current_process.argtypes = []
        get_current_process.restype = wintypes.HANDLE
        process = get_current_process()
    except (AttributeError, OSError) as error:
        logger.warning("Unable to access the current process for Efficiency mode: %s", error)
        return False

    priority_enabled = False
    try:
        set_priority_class = kernel32.SetPriorityClass
        set_priority_class.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        set_priority_class.restype = wintypes.BOOL
        priority_enabled = bool(set_priority_class(process, IDLE_PRIORITY_CLASS))
        if not priority_enabled:
            logger.warning("Unable to enable low process priority; Windows error %s", _last_error(kernel32))
    except (AttributeError, OSError) as error:
        logger.warning("Unable to enable low process priority: %s", error)

    eco_qos_enabled = False
    try:
        set_process_information = kernel32.SetProcessInformation
        set_process_information.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        ]
        set_process_information.restype = wintypes.BOOL
        state = ProcessPowerThrottlingState(
            Version=PROCESS_POWER_THROTTLING_CURRENT_VERSION,
            ControlMask=PROCESS_POWER_THROTTLING_EXECUTION_SPEED,
            StateMask=PROCESS_POWER_THROTTLING_EXECUTION_SPEED,
        )
        eco_qos_enabled = bool(
            set_process_information(
                process,
                PROCESS_POWER_THROTTLING,
                ctypes.byref(state),
                ctypes.sizeof(state),
            )
        )
        if not eco_qos_enabled:
            logger.warning("Unable to enable EcoQoS; Windows error %s", _last_error(kernel32))
    except (AttributeError, OSError) as error:
        logger.warning("Unable to enable EcoQoS: %s", error)

    return priority_enabled and eco_qos_enabled
