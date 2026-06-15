"""Tap Strap BLE manager — refactored from collect_gestures.py:GestureCollector.

Differences from the original script:
  - No print()/UI; surfaces state via callbacks (on_state, on_ready, on_error)
    so the Tk layer can drive the UI.
  - Explicit handling of unauthorized / powered-off Bluetooth states (critical
    inside a packaged .app where macOS TCC can deny BLE).
  - Always parses incoming frames to keep a small `recent` ring buffer (for the
    live waveform) and track `max_accl_channels`; only appends to the trial
    buffer while `collecting` is True.

Connection method is the proven one: retrieveConnectedPeripheralsWithServices_
(the Tap must be connected to this Mac as a keyboard first), then attach as a
second central and switch it to raw mode — no pairing dance, keyboard stays up.
"""
import time
from collections import deque

import objc
from CoreBluetooth import CBCharacteristicWriteWithoutResponse
from Foundation import NSObject

from .constants import (
    TAP_SERVICE_UUID, NUS_SERVICE_UUID,
    NUS_RX_FRAGMENT, NUS_TX_FRAGMENT,
    CMD_CONTROLLER, CMD_RAW, CMD_TEXT,
)
from .parser import parse_raw

# CBManagerState values
CB_STATE_UNKNOWN = 0
CB_STATE_RESETTING = 1
CB_STATE_UNSUPPORTED = 2
CB_STATE_UNAUTHORIZED = 3
CB_STATE_POWERED_OFF = 4
CB_STATE_POWERED_ON = 5

_STATE_NAMES = {
    0: "unknown", 1: "resetting", 2: "unsupported",
    3: "unauthorized", 4: "powered_off", 5: "powered_on",
}


class TapBleManager(NSObject):
    """CoreBluetooth central + peripheral delegate for the Tap Strap.

    Set the callback attributes after alloc().init():
        on_state(state_name: str)   - bluetooth adapter state changes
        on_ready()                  - device connected + raw mode armed
        on_error(message: str)      - connection / discovery failure
    """

    def init(self):
        self = objc.super(TapBleManager, self).init()
        self.central = None
        self.peripheral = None
        self.characteristics = {}
        self.services_discovered = 0
        self.expected_services = 2
        self.phase = "init"          # init -> discover -> ready -> done
        self.collecting = False
        self.raw_buffer = []         # current trial's frames (when collecting)
        self.packet_count = 0
        self.recent = deque(maxlen=300)   # live tap for waveform (always updated)
        self.max_accl_channels = 0
        self.device_name = None
        self.device_uuid = None
        # callbacks (set by app); default no-ops
        self.on_state = lambda s: None
        self.on_ready = lambda: None
        self.on_error = lambda m: None
        return self

    # ---- CBCentralManagerDelegate ----

    def centralManagerDidUpdateState_(self, central):
        self.central = central
        state = central.state()
        self.on_state(_STATE_NAMES.get(state, str(state)))
        if state == CB_STATE_POWERED_ON:
            self._find_and_connect(central)
        elif state == CB_STATE_UNAUTHORIZED:
            self.on_error("Bluetooth permission denied. Grant it in System "
                          "Settings > Privacy & Security > Bluetooth.")
        elif state == CB_STATE_POWERED_OFF:
            self.on_error("Bluetooth is off. Turn it on.")

    def _find_and_connect(self, central):
        peris = central.retrieveConnectedPeripheralsWithServices_([TAP_SERVICE_UUID])
        if peris and len(peris) > 0:
            self.peripheral = peris[0]
            self.peripheral.setDelegate_(self)
            self.device_name = self.peripheral.name() or "Tap"
            try:
                self.device_uuid = str(self.peripheral.identifier().UUIDString())
            except Exception:
                self.device_uuid = None
            central.connectPeripheral_options_(self.peripheral, None)
        else:
            self.phase = "done"
            self.on_error("Tap not found. Connect it to this Mac as a keyboard "
                          "first (System Settings > Bluetooth), then tap fingers "
                          "to wake it.")

    def centralManager_didConnectPeripheral_(self, central, peripheral):
        self.phase = "discover"
        peripheral.discoverServices_([TAP_SERVICE_UUID, NUS_SERVICE_UUID])

    def centralManager_didFailToConnectPeripheral_error_(self, central, peripheral, error):
        self.phase = "done"
        self.on_error(f"Connection failed: {error}")

    def centralManager_didDisconnectPeripheral_error_(self, central, peripheral, error):
        self.phase = "done"
        self.on_error(f"Disconnected: {error}")

    # ---- CBPeripheralDelegate ----

    def peripheral_didDiscoverServices_(self, peripheral, error):
        if error:
            self.phase = "done"
            self.on_error(f"Service discovery error: {error}")
            return
        for service in peripheral.services():
            peripheral.discoverCharacteristics_forService_(None, service)

    def peripheral_didDiscoverCharacteristicsForService_error_(self, peripheral, service, error):
        if error:
            return
        for char in service.characteristics():
            self.characteristics[str(char.UUID()).lower()] = char
        self.services_discovered += 1
        if self.services_discovered >= self.expected_services:
            self._setup_raw_mode()

    def _setup_raw_mode(self):
        # subscribe to any notify characteristic
        for char in self.characteristics.values():
            if char.properties() & 0x10:
                self.peripheral.setNotifyValue_forCharacteristic_(True, char)
        # controller mode (keyboard off) -> raw mode
        self._write_mode(CMD_CONTROLLER)
        time.sleep(0.3)
        self._write_mode(CMD_RAW)
        self.phase = "ready"
        self.on_ready()

    def _write_mode(self, cmd):
        for key, char in self.characteristics.items():
            if NUS_RX_FRAGMENT in key:
                data = objc.lookUpClass("NSData").dataWithBytes_length_(cmd, len(cmd))
                self.peripheral.writeValue_forCharacteristic_type_(
                    data, char, CBCharacteristicWriteWithoutResponse)
                return

    def peripheral_didUpdateValueForCharacteristic_error_(self, peripheral, characteristic, error):
        if error:
            return
        if NUS_TX_FRAGMENT not in str(characteristic.UUID()).lower():
            return
        data = characteristic.value()
        if data is None:
            return
        recv_time = time.time()
        for m in parse_raw(bytes(data)):
            m["recv_time"] = recv_time
            self.recent.append(m)
            if m["type"] == "accl":
                ch = len(m["payload"])
                if ch > self.max_accl_channels:
                    self.max_accl_channels = ch
            if self.collecting:
                self.raw_buffer.append(m)
                self.packet_count += 1

    def peripheral_didUpdateNotificationStateForCharacteristic_error_(self, p, c, e):
        pass

    def peripheral_didWriteValueForCharacteristic_error_(self, p, c, e):
        pass

    # ---- trial control ----

    def refresh_raw_mode(self):
        """Re-arm raw mode (keyboard stays off). Call periodically during a session."""
        self._write_mode(CMD_CONTROLLER)
        self._write_mode(CMD_RAW)

    def start_collecting(self):
        self.raw_buffer = []
        self.packet_count = 0
        self.collecting = True

    def stop_collecting(self):
        self.collecting = False
        return list(self.raw_buffer)

    def finish(self):
        """Restore keyboard mode before exit."""
        try:
            self._write_mode(CMD_TEXT)
        except Exception:
            pass
