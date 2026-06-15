"""Tap Strap 2 BLE constants — ported verbatim from finger/tapstrap/collect_gestures.py.

These are the GATT UUIDs and raw-mode command bytes for the Tap Strap 2. The
15-channel (5-finger) accelerometer stream requires TapManager "Developer Mode"
to be enabled on the device — a deployment precondition, not a code setting.
"""
from CoreBluetooth import CBUUID

# GATT services / characteristics
TAP_SERVICE_UUID = CBUUID.UUIDWithString_("c3ff0001-1d8b-40fd-a56f-c7bd5d0f3370")
NUS_SERVICE_UUID = CBUUID.UUIDWithString_("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
RAW_SENSOR_UUID = CBUUID.UUIDWithString_("6e400003-b5a3-f393-e0a9-e50e24dcca9e")

# NUS characteristic UUID fragments (matched as substrings on discovered chars)
NUS_RX_FRAGMENT = "6e400002"   # write commands here
NUS_TX_FRAGMENT = "6e400003"   # raw sensor notifications arrive here

# Mode commands
CMD_CONTROLLER = bytes([0x3, 0xC, 0x0, 0x1])         # disable keyboard / controller mode
CMD_RAW = bytes([0x3, 0xC, 0x0, 0xA, 0, 0, 0])       # enable raw sensor streaming (7 bytes)
CMD_TEXT = bytes([0x3, 0xC, 0x0, 0x0])               # restore keyboard mode (on exit)

# Raw packet framing: timestamp high bit set => accelerometer frame, else IMU.
RAW_MSG_TYPE_BIT = 2 ** 31

# Channel counts
ACCL_CHANNELS_FULL = 15   # 5 fingers x XYZ (Developer Mode on)
IMU_CHANNELS = 6          # gyro xyz + accel xyz
