package com.research.tapstrap.data.ble

import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.content.Context
import android.os.Build
import android.util.Log
import com.research.tapstrap.data.parser.RawParser
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.launch
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

/**
 * BLE client for Tap Strap 2.
 *
 * Exposes:
 *   - state: connection / MTU / device address
 *   - packets(): a Flow<BlePacket> of raw notify payloads (only while connected & subscribed)
 *
 * Critical line vs the Mac version:
 *   gatt.requestMtu(517)  -> macOS CoreBluetooth cannot do this.
 */
@SuppressLint("MissingPermission")
@Singleton
class TapStrapClient @Inject constructor(@ApplicationContext private val context: Context) {

    sealed interface Connection {
        data object Idle : Connection
        data object Scanning : Connection
        data class Connecting(val mac: String) : Connection
        data class Connected(val mac: String, val mtu: Int) : Connection
        data class Failed(val reason: String) : Connection
    }

    data class BlePacket(val recvTimeMs: Long, val bytes: ByteArray) {
        override fun equals(other: Any?) = other is BlePacket && bytes.contentEquals(other.bytes) && recvTimeMs == other.recvTimeMs
        override fun hashCode(): Int = 31 * recvTimeMs.hashCode() + bytes.contentHashCode()
    }

    companion object {
        private const val TAG = "TapStrap"
        private val NUS_SERVICE = UUID.fromString("6e400001-b5a3-f393-e0a9-e50e24dcca9e")
        private val NUS_RX = UUID.fromString("6e400002-b5a3-f393-e0a9-e50e24dcca9e")
        private val NUS_TX = UUID.fromString("6e400003-b5a3-f393-e0a9-e50e24dcca9e")
        private val CCCD = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb")

        // Standard BLE Device Information Service (0x180A) — read the Tap's
        // firmware/hardware/manufacturer strings to pin down exactly which
        // firmware is on this strap (the suspected source of the MTU=23 cap).
        private val DIS_SERVICE = UUID.fromString("0000180a-0000-1000-8000-00805f9b34fb")
        private val DIS_FIRMWARE_REV = UUID.fromString("00002a26-0000-1000-8000-00805f9b34fb")
        private val DIS_HARDWARE_REV = UUID.fromString("00002a27-0000-1000-8000-00805f9b34fb")
        private val DIS_SOFTWARE_REV = UUID.fromString("00002a28-0000-1000-8000-00805f9b34fb")
        private val DIS_MANUFACTURER  = UUID.fromString("00002a29-0000-1000-8000-00805f9b34fb")

        // Tap Strap "Controller mode" command — keeps the keyboard chord recognizer off.
        // Source of truth: finger/tapstrap/collect_gestures.py line 38.
        private val CMD_CONTROLLER = byteArrayOf(0x03, 0x0C, 0x00, 0x01)

        // Tap Strap "Raw sensor mode" command — 7 bytes, with 3 trailing zeros.
        // Source of truth: finger/tapstrap/collect_gestures.py line 39.
        // (Our earlier 4-byte version was wrong — the firmware silently
        // dropped the command, leaving the device in keyboard mode and never
        // emitting notifications.)
        private val CMD_RAW = byteArrayOf(0x03, 0x0C, 0x00, 0x0A, 0x00, 0x00, 0x00)

        // Interval between CMD_CONTROLLER and CMD_RAW, and between refresh
        // rounds. Matches the Mac `time.sleep(0.3)` cadence in _setup_raw_mode.
        private const val CMD_GAP_MS = 300L

        // Number of times to re-arm raw mode at connect — Mac runs the
        // refresh sequence 3 times before believing the device is in raw mode.
        private const val RAW_REFRESH_ROUNDS = 3
    }

    private val _conn = MutableStateFlow<Connection>(Connection.Idle)
    val conn: StateFlow<Connection> = _conn

    // Maximum accl channel count observed since session start.
    // 8 = macOS-equivalent truncation; 15 = full 5-finger breakthrough.
    private val _maxAcclChannels = MutableStateFlow(0)
    val maxAcclChannels: StateFlow<Int> = _maxAcclChannels.asStateFlow()

    private val _packetCount = MutableStateFlow(0)
    val packetCount: StateFlow<Int> = _packetCount.asStateFlow()

    private val btManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
    private val adapter = btManager.adapter
    private var gatt: BluetoothGatt? = null
    private var rxChar: BluetoothGattCharacteristic? = null

    // Pending Device-Information-Service reads, drained one at a time (GATT
    // operations must be serialized) before we enter raw-sensor mode.
    private val disReadQueue = ArrayDeque<BluetoothGattCharacteristic>()

    // Background scope used for the timed raw-mode arming sequence. Lives as
    // long as the singleton; supervised so a failure on one connection cycle
    // doesn't poison future ones.
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var rawArmJob: Job? = null

    private var packetEmit: ((BlePacket) -> Unit)? = null

    /** Hot-ish flow: subscribers receive packets while connection is active. */
    fun packets(): Flow<BlePacket> = callbackFlow {
        val cb: (BlePacket) -> Unit = { trySend(it) }
        packetEmit = cb
        awaitClose { if (packetEmit === cb) packetEmit = null }
    }

    fun scanAndConnect() {
        if (adapter == null || !adapter.isEnabled) {
            _conn.value = Connection.Failed("Bluetooth is OFF")
            return
        }
        // Prefer a direct connect to an already-bonded Tap. Once paired (and held
        // by the system as an HID device), the Tap usually stops advertising, so a
        // BLE scan won't surface it — but we can still open our own GATT link by
        // address. Fall back to scanning only if no bonded Tap is found.
        val bondedTap = try {
            adapter.bondedDevices?.firstOrNull { (it.name ?: "").contains("Tap", true) }
        } catch (_: SecurityException) { null }

        if (bondedTap != null) {
            Log.d(TAG, "Found bonded Tap ${bondedTap.address}; connecting directly (no scan)")
            connect(bondedTap)
            return
        }

        val scanner = adapter.bluetoothLeScanner
        if (scanner == null) {
            _conn.value = Connection.Failed("BLE scanner unavailable")
            return
        }
        Log.d(TAG, "No bonded Tap; starting BLE scan")
        _conn.value = Connection.Scanning
        scanner.startScan(scanCallback)
    }

    fun disconnect() {
        adapter?.bluetoothLeScanner?.stopScan(scanCallback)
        rawArmJob?.cancel()
        rawArmJob = null
        gatt?.disconnect()
        gatt?.close()
        gatt = null
        rxChar = null
        _conn.value = Connection.Idle
        _maxAcclChannels.value = 0
        _packetCount.value = 0
    }

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val name = result.device.name ?: return
            if (name.contains("Tap", ignoreCase = true)) {
                adapter?.bluetoothLeScanner?.stopScan(this)
                connect(result.device)
            }
        }
        override fun onScanFailed(errorCode: Int) {
            _conn.value = Connection.Failed("Scan failed: $errorCode")
        }
    }

    private fun connect(device: BluetoothDevice) {
        _conn.value = Connection.Connecting(device.address)
        // Force BLE transport. The Tap is a dual-mode device (advertises an HID
        // keyboard over BR/EDR AND a BLE GATT server). Without an explicit
        // transport, Android may attach over the wrong one or bounce between
        // HID and LE, which (a) destabilises the link and (b) can leave MTU
        // negotiation stuck at the 23-byte default. TRANSPORT_LE pins us to the
        // clean BLE path where the ATT MTU exchange actually happens.
        gatt = device.connectGatt(context, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
    }

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            when (newState) {
                BluetoothProfile.STATE_CONNECTED -> {
                    // CRITICAL: Android GATT operations must be SERIALIZED — issue
                    // exactly one, wait for its callback, then the next. Our old
                    // code fired requestConnectionPriority() and requestMtu()
                    // back-to-back; on Samsung the MTU request was silently
                    // dropped and the link fell back to the default ATT MTU 23.
                    // The official Tap SDK uses a one-at-a-time GattExecutor queue
                    // for exactly this reason.
                    //
                    // So here we issue ONLY requestMtu. Connection priority is
                    // requested later, after onMtuChanged, when the bus is free.
                    // A short delay lets bonding/encryption settle first — some
                    // firmwares only grant a large MTU over an encrypted link.
                    Log.d(TAG, "Connected to ${g.device.address}; scheduling MTU request")
                    rawArmJob?.cancel()
                    rawArmJob = scope.launch {
                        delay(600)               // let encryption/bond settle
                        val ok = g.requestMtu(247)
                        Log.d(TAG, "requestMtu(247) issued -> $ok")
                    }
                }
                BluetoothProfile.STATE_DISCONNECTED -> {
                    Log.d(TAG, "Disconnected (status=$status)")
                    _conn.value = Connection.Idle
                }
            }
        }

        override fun onMtuChanged(g: BluetoothGatt, mtu: Int, status: Int) {
            Log.d(TAG, "MTU negotiated: $mtu (status=$status)")
            _conn.value = Connection.Connected(g.device.address, mtu)
            // NOTE: deliberately NOT requesting CONNECTION_PRIORITY_HIGH here.
            // The 7.5ms high-priority interval was destabilising the link
            // (status=8 supervision timeouts) while the system also held the Tap
            // as HID. Stay on the default/balanced interval for this MTU probe;
            // re-add HIGH only once MTU≥37 is confirmed and the HID conflict is
            // resolved.
            g.discoverServices()
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            Log.d(TAG, "onServicesDiscovered status=$status")
            if (status != BluetoothGatt.GATT_SUCCESS) {
                _conn.value = Connection.Failed("Service discovery failed: $status"); return
            }
            val nus = g.getService(NUS_SERVICE) ?: run {
                Log.e(TAG, "NUS_SERVICE not in advertised services")
                _conn.value = Connection.Failed("NUS service missing"); return
            }
            val tx = nus.getCharacteristic(NUS_TX)
            val rx = nus.getCharacteristic(NUS_RX)
            if (tx == null || rx == null) {
                _conn.value = Connection.Failed("NUS characteristics missing"); return
            }
            rxChar = rx
            // DIS firmware read is auth-gated (status=137) and just stalls the
            // flow for 30s on an unbonded link — skip it. Firmware confirmed
            // 3.30 via TapManager. Go straight to enabling raw mode.
            enableNotifyAndArm(g, tx)
        }

        @Deprecated("legacy read callback kept for broad compat")
        override fun onCharacteristicRead(g: BluetoothGatt, ch: BluetoothGattCharacteristic, status: Int) {
            handleDisRead(g, ch, ch.value, status)
        }

        override fun onCharacteristicRead(
            g: BluetoothGatt, ch: BluetoothGattCharacteristic, value: ByteArray, status: Int
        ) {
            handleDisRead(g, ch, value, status)
        }

        private fun handleDisRead(
            g: BluetoothGatt, ch: BluetoothGattCharacteristic, value: ByteArray?, status: Int
        ) {
            val label = when (ch.uuid) {
                DIS_FIRMWARE_REV -> "FIRMWARE_REV"
                DIS_HARDWARE_REV -> "HARDWARE_REV"
                DIS_SOFTWARE_REV -> "SOFTWARE_REV(bootloader)"
                DIS_MANUFACTURER -> "MANUFACTURER"
                else -> ch.uuid.toString()
            }
            val str = value?.toString(Charsets.UTF_8)?.trim() ?: "(null)"
            Log.d(TAG, "DIS  $label = \"$str\"  (status=$status)")
            // Continue draining the read queue; when empty, start raw mode.
            val next = if (disReadQueue.isNotEmpty()) disReadQueue.removeAt(0) else null
            if (next != null) {
                g.readCharacteristic(next)
            } else {
                val tx = g.getService(NUS_SERVICE)?.getCharacteristic(NUS_TX) ?: return
                enableNotifyAndArm(g, tx)
            }
        }

        private fun enableNotifyAndArm(g: BluetoothGatt, tx: BluetoothGattCharacteristic) {
            val ok = g.setCharacteristicNotification(tx, true)
            Log.d(TAG, "setCharacteristicNotification(TX, true) -> $ok")
            val cccd = tx.getDescriptor(CCCD) ?: run {
                Log.e(TAG, "CCCD descriptor missing on TX characteristic")
                _conn.value = Connection.Failed("CCCD missing"); return
            }
            writeCccdEnableNotify(g, cccd)
        }

        override fun onDescriptorWrite(g: BluetoothGatt, desc: BluetoothGattDescriptor, status: Int) {
            Log.d(TAG, "onDescriptorWrite uuid=${desc.uuid} status=$status")
            if (desc.uuid != CCCD) return
            if (status != BluetoothGatt.GATT_SUCCESS) {
                _conn.value = Connection.Failed("CCCD write failed: $status"); return
            }
            // Notifications enabled at the GATT layer; now arm raw mode by
            // sending CMD_CONTROLLER + CMD_RAW with the Mac-script cadence.
            val rx = rxChar ?: return
            rawArmJob?.cancel()
            rawArmJob = scope.launch { armRawMode(g, rx) }
        }

        // We DO NOT rely on onCharacteristicWrite for the command sequencing.
        // Mac uses WRITE_WITHOUT_RESPONSE and just sleeps; we do the same in
        // armRawMode() below. Log the callback purely for diagnostics.
        override fun onCharacteristicWrite(g: BluetoothGatt, ch: BluetoothGattCharacteristic, status: Int) {
            Log.d(TAG, "onCharacteristicWrite uuid=${ch.uuid} status=$status")
        }

        @Deprecated("legacy API kept for pre-Android-13 devices")
        override fun onCharacteristicChanged(g: BluetoothGatt, ch: BluetoothGattCharacteristic) {
            val bytes = ch.value ?: return
            Log.d(TAG, "notify(legacy) size=${bytes.size}")
            handleNotification(bytes)
        }

        // Android 13 (API 33) + : new callback signature with explicit value param.
        // Some OEM ROMs (notably Samsung One UI on Android 14) fire ONLY this one
        // and do NOT auto-bridge to the deprecated method.
        override fun onCharacteristicChanged(
            g: BluetoothGatt,
            ch: BluetoothGattCharacteristic,
            value: ByteArray,
        ) {
            Log.d(TAG, "notify(api33) size=${value.size}")
            handleNotification(value)
        }

        private fun handleNotification(bytes: ByteArray) {
            // Diagnostic: dump the FULL hex of the first 40 notifications, plus a
            // decoded header (timestamp + accl/imu type). Goal: determine whether
            // the firmware, at MTU 23, fragments a 34-byte 5-finger (Device) frame
            // across two 20-byte notifications (recoverable by reassembly) or
            // truly drops ring+pinky (not recoverable without a larger MTU).
            if (_packetCount.value < 40) {
                val full = bytes.joinToString(" ") { "%02x".format(it) }
                val ts32 = ((bytes.getOrElse(3){0}.toLong() and 0xff) shl 24) or
                           ((bytes.getOrElse(2){0}.toLong() and 0xff) shl 16) or
                           ((bytes.getOrElse(1){0}.toLong() and 0xff) shl 8)  or
                           (bytes.getOrElse(0){0}.toLong() and 0xff)
                val isAccl = (ts32 and 0x80000000L) != 0L
                val ts = ts32 and 0x7fffffffL
                Log.d(TAG, "raw[${_packetCount.value}] sz=${bytes.size} " +
                          "type=${if (isAccl) "ACCL" else "imu "} ts=$ts | $full")
            }
            val parsed = RawParser.parse(bytes)
            val acclMax = parsed.filter { it.type == "accl" }.maxOfOrNull { it.nActual } ?: 0
            if (acclMax > 0) {
                val cur = _maxAcclChannels.value
                if (acclMax > cur) _maxAcclChannels.value = acclMax
            }
            _packetCount.value = _packetCount.value + 1
            packetEmit?.invoke(BlePacket(System.currentTimeMillis(), bytes))
        }
    }

    // -------------------------------------------------------------------------
    // Raw-mode arming sequence — must mirror Mac collect_gestures.py.
    //
    // Mac flow (collect_gestures.py:_setup_raw_mode + refresh_raw_mode):
    //     write(CMD_CONTROLLER, WriteWithoutResponse)
    //     sleep(0.3)
    //     write(CMD_RAW,        WriteWithoutResponse)
    //     ... and the caller then re-runs that pair 3 times before collecting.
    //
    // Critical details we missed before:
    //   1. CMD_RAW is 7 bytes, not 4 (3 trailing zeros).
    //   2. WRITE_TYPE_NO_RESPONSE, not the default WRITE_TYPE_DEFAULT.
    //   3. 300 ms gap between writes, not chained on callbacks.
    //   4. 3 refresh rounds; firmware sometimes doesn't latch on the first.
    // -------------------------------------------------------------------------

    private suspend fun armRawMode(g: BluetoothGatt, rx: BluetoothGattCharacteristic) {
        Log.d(TAG, "armRawMode: starting $RAW_REFRESH_ROUNDS rounds")
        repeat(RAW_REFRESH_ROUNDS) { round ->
            val ctrlOk = writeNoResponse(g, rx, CMD_CONTROLLER)
            Log.d(TAG, "armRawMode round=$round CMD_CONTROLLER -> $ctrlOk")
            delay(CMD_GAP_MS)
            val rawOk = writeNoResponse(g, rx, CMD_RAW)
            Log.d(TAG, "armRawMode round=$round CMD_RAW -> $rawOk")
            delay(CMD_GAP_MS)
        }
        Log.d(TAG, "armRawMode: complete; expecting notifications now")
    }

    // -------------------------------------------------------------------------
    // Version-aware BLE write helpers
    //
    // Android 13 (API 33) deprecated the old "set value on object, then call
    // writeXxx()" pattern in favour of explicit (object, value, writeType)
    // overloads. On some OEM ROMs the deprecated path silently no-ops, which
    // is consistent with our "Raw mode active logged but no notifications"
    // symptom. We use the new API on API 33+ and fall back to the old one
    // for older devices we might ever ship on.
    // -------------------------------------------------------------------------

    private fun writeNoResponse(
        g: BluetoothGatt,
        ch: BluetoothGattCharacteristic,
        value: ByteArray,
    ): String {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val rc = g.writeCharacteristic(
                ch, value, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            )
            if (rc == BluetoothStatusCodes.SUCCESS) "SUCCESS" else "rc=$rc"
        } else {
            @Suppress("DEPRECATION")
            ch.value = value
            @Suppress("DEPRECATION")
            ch.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
            @Suppress("DEPRECATION")
            if (g.writeCharacteristic(ch)) "queued" else "FAILED"
        }
    }

    private fun writeCccdEnableNotify(g: BluetoothGatt, cccd: BluetoothGattDescriptor) {
        val value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
        val result = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val rc = g.writeDescriptor(cccd, value)
            if (rc == BluetoothStatusCodes.SUCCESS) "SUCCESS" else "rc=$rc"
        } else {
            @Suppress("DEPRECATION")
            cccd.value = value
            @Suppress("DEPRECATION")
            if (g.writeDescriptor(cccd)) "queued" else "FAILED"
        }
        Log.d(TAG, "writeCccdEnableNotify -> $result")
    }
}
