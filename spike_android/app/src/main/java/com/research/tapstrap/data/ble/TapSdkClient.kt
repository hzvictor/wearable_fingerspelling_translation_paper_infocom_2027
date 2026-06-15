package com.research.tapstrap.data.ble

import android.content.Context
import android.util.Log
import com.tapwithus.sdk.TapListener
import com.tapwithus.sdk.TapSdk
import com.tapwithus.sdk.TapSdkFactory
import com.tapwithus.sdk.airmouse.AirMousePacket
import com.tapwithus.sdk.mouse.MousePacket
import com.tapwithus.sdk.mode.RawSensorData
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.callbackFlow
import javax.inject.Inject
import javax.inject.Singleton

/**
 * BLE client built on top of the OFFICIAL TapWithUs Android SDK.
 *
 * Why we have this in addition to [TapStrapClient]:
 *   Our hand-rolled GATT client (TapStrapClient) hits an 8-channel accelerometer
 *   ceiling because each BLE notification it receives is 20 bytes = 4-byte ts +
 *   8 × uint16 channels. The Tap firmware streams 5-finger × 3-axis data, so the
 *   34-byte full frame either gets truncated at the source or fragmented across
 *   notifications and our parser misses the second half.
 *
 *   FingerSpeller (Leng et al.) ran on Pixel 4a using this same official SDK
 *   and produced verifiable 15-channel data (we sanity-checked their dataset).
 *   This client wraps the SDK so we can A/B against our hand-rolled implementation
 *   and resolve whether the missing channels are recoverable.
 *
 * Exposes the same shape of state flows as [TapStrapClient] so DeviceViewModel
 * can drive the same UI:
 *   - conn:             Idle / Connecting / Connected
 *   - maxAcclChannels:  highest non-null finger channels seen (target = 15)
 *   - packetCount:      total raw-sensor callbacks received
 *
 * SDK behavior worth knowing:
 *   - Auto-connects to any paired TAP device — no manual scan/connect needed.
 *   - On connect, defaults to Controller mode (keyboard suppressed).
 *   - We must explicitly call startRawSensorMode(...) to enable streaming.
 *   - Callbacks arrive on a worker thread; we don't post to the main thread
 *     because all StateFlow updates are safe from any thread.
 */
@Singleton
class TapSdkClient @Inject constructor(
    @ApplicationContext private val context: Context,
) {

    sealed interface Connection {
        data object Idle : Connection
        data class Connecting(val mac: String) : Connection
        data class Connected(val mac: String) : Connection
        data class Failed(val reason: String) : Connection
    }

    data class RawSamplePacket(val recvTimeMs: Long, val nFingersValid: Int, val nImuValid: Int)

    companion object {
        private const val TAG = "TapSdkClient"

        // Sensitivity bytes: 0 means "use the device's default sensitivity".
        // Range per README: deviceAccel 1..4, imuGyro 1..4, imuAccel 1..5.
        private const val SENS_DEFAULT: Byte = 0
    }

    private val _conn = MutableStateFlow<Connection>(Connection.Idle)
    val conn: StateFlow<Connection> = _conn.asStateFlow()

    private val _maxAcclChannels = MutableStateFlow(0)
    val maxAcclChannels: StateFlow<Int> = _maxAcclChannels.asStateFlow()

    private val _packetCount = MutableStateFlow(0)
    val packetCount: StateFlow<Int> = _packetCount.asStateFlow()

    private val _maxPacketBytes = MutableStateFlow(0)
    val maxPacketBytes: StateFlow<Int> = _maxPacketBytes.asStateFlow()

    private val sdk: TapSdk by lazy {
        TapSdkFactory.getDefault(context).also {
            it.registerTapListener(listener)
            // Pause + resume forces the SDK to (re)kick off Bluetooth state checks
            // and start auto-connecting to paired TAPs.
            it.resume()
        }
    }

    private var emit: ((RawSamplePacket) -> Unit)? = null

    // One-shot guard so we dump the first 5-finger frame's raw values exactly once.
    @Volatile private var loggedFirstDevice = false

    fun packets(): Flow<RawSamplePacket> = callbackFlow {
        val cb: (RawSamplePacket) -> Unit = { trySend(it) }
        emit = cb
        awaitClose { if (emit === cb) emit = null }
    }

    /**
     * The SDK auto-connects to any paired TAP. This call exists so the UI's
     * "Scan & Connect" button has something to invoke — it just makes sure
     * the SDK is alive and the listener is registered. The user must have
     * already paired the TAP via the system Bluetooth settings.
     */
    fun start() {
        sdk  // touches the lazy: triggers init + listener register + resume
        _conn.value = Connection.Connecting(mac = "(auto-detect)")
        // Also enable verbose SDK logs to logcat to ease diagnosis.
        try { sdk.enableDebug() } catch (_: Throwable) { /* older SDK might lack it */ }
    }

    fun stop() {
        try { sdk.pause() } catch (_: Throwable) {}
        _conn.value = Connection.Idle
        _maxAcclChannels.value = 0
        _packetCount.value = 0
        _maxPacketBytes.value = 0
        loggedFirstDevice = false
    }

    // ---- TapListener ---------------------------------------------------------

    private val listener = object : TapListener {

        override fun onBluetoothTurnedOn() {
            Log.d(TAG, "BT turned on")
        }

        override fun onBluetoothTurnedOff() {
            Log.d(TAG, "BT turned off")
            _conn.value = Connection.Failed("Bluetooth off")
        }

        override fun onTapStartConnecting(tapIdentifier: String) {
            Log.d(TAG, "start connecting: $tapIdentifier")
            _conn.value = Connection.Connecting(tapIdentifier)
        }

        override fun onTapConnected(tapIdentifier: String) {
            Log.d(TAG, "connected: $tapIdentifier — starting raw sensor mode")
            _conn.value = Connection.Connected(tapIdentifier)
            try {
                sdk.startRawSensorMode(tapIdentifier, SENS_DEFAULT, SENS_DEFAULT, SENS_DEFAULT)
            } catch (t: Throwable) {
                Log.e(TAG, "startRawSensorMode failed", t)
                _conn.value = Connection.Failed("startRawSensorMode: ${t.message}")
            }
        }

        override fun onTapDisconnected(tapIdentifier: String) {
            Log.d(TAG, "disconnected: $tapIdentifier")
            _conn.value = Connection.Idle
        }

        override fun onTapResumed(tapIdentifier: String) {
            Log.d(TAG, "tap resumed: $tapIdentifier")
            // After resume the SDK may revert to Controller mode; re-arm raw.
            try {
                sdk.startRawSensorMode(tapIdentifier, SENS_DEFAULT, SENS_DEFAULT, SENS_DEFAULT)
            } catch (_: Throwable) {}
        }

        override fun onTapChanged(tapIdentifier: String) { /* no-op */ }

        override fun onTapInputReceived(tapIdentifier: String, data: Int, repeatData: Int) {
            // Tap input (chorded fingers as text-mode integer) — we don't care
            // about this for the spike. Log lightly.
            // Log.v(TAG, "tap input: data=$data")
        }

        override fun onTapShiftSwitchReceived(tapIdentifier: String, data: Int) { /* no-op */ }

        override fun onMouseInputReceived(tapIdentifier: String, data: MousePacket) { /* no-op */ }

        override fun onAirMouseInputReceived(tapIdentifier: String, data: AirMousePacket) { /* no-op */ }

        override fun onRawSensorInputReceived(
            tapIdentifier: String,
            rsData: com.tapwithus.sdk.mode.RawSensorData,
        ) {
            // RawSensorData is a parsed event — either a 5-finger accelerometer
            // sample (DataType.Device) or a thumb IMU sample (DataType.IMU on
            // Tap Strap 2 / TapXR). It carries a timestamp + Point3 array.
            val type = rsData.dataType
            val nFingers = if (type == RawSensorData.DataType.Device) {
                var n = 0
                for (i in intArrayOf(
                    RawSensorData.iDEV_THUMB,
                    RawSensorData.iDEV_INDEX,
                    RawSensorData.iDEV_MIDDLE,
                    RawSensorData.iDEV_RING,
                    RawSensorData.iDEV_PINKY,
                )) {
                    if (rsData.getPoint(i) != null) n++
                }
                n  // 0..5 fingers with valid data this sample
            } else 0

            val nImu = if (type == RawSensorData.DataType.IMU) {
                // IMU sample = gyro XYZ + accel XYZ = 6 channels by definition
                6
            } else 0

            // Channel count = nFingers * 3 axes (matches our maxAccl semantics)
            val acclChannels = nFingers * 3
            if (acclChannels > _maxAcclChannels.value) {
                _maxAcclChannels.value = acclChannels
            }
            _packetCount.value = _packetCount.value + 1

            // Diagnostic: log the FIRST Device (5-finger) frame in full, plus a
            // periodic summary, so we can confirm 15-channel data without
            // relying on the on-screen number.
            if (type == RawSensorData.DataType.Device && !loggedFirstDevice) {
                loggedFirstDevice = true
                val sb = StringBuilder("FIRST DEVICE FRAME fingers=$nFingers  ")
                for (i in 0 until (rsData.points?.size ?: 0)) {
                    val p = rsData.getPoint(i)
                    sb.append(if (p != null) "[%.0f,%.0f,%.0f]".format(p.x, p.y, p.z) else "[null]")
                }
                Log.d(TAG, sb.toString())
            }
            if (_packetCount.value % 50 == 0) {
                Log.d(TAG, "summary total#=${_packetCount.value} " +
                          "maxAccl=${_maxAcclChannels.value} thisType=$type fingers=$nFingers")
            }

            emit?.invoke(RawSamplePacket(System.currentTimeMillis(), nFingers, nImu))
        }

        override fun onTapChangedState(tapIdentifier: String, state: Int) {
            Log.d(TAG, "tap state changed: $tapIdentifier state=$state")
        }

        override fun onError(tapIdentifier: String, code: Int, description: String) {
            Log.e(TAG, "error: $tapIdentifier code=$code desc=$description")
            _conn.value = Connection.Failed("SDK error $code: $description")
        }
    }
}
