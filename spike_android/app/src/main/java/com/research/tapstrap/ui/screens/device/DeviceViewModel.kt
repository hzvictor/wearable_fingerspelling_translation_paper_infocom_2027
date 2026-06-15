package com.research.tapstrap.ui.screens.device

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.research.tapstrap.data.ble.TapSdkClient
import com.research.tapstrap.data.ble.TapStrapClient
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * UI state for the spike's Device screen.
 *
 * Both `conn` and the metrics are sourced from [TapSdkClient] in this build —
 * we are A/B testing whether the official TapWithUs SDK exposes the missing
 * 5th-finger channels (rings + pinky) that our hand-rolled [TapStrapClient]
 * cannot recover.
 *
 * The metrics meaning under the SDK build:
 *   - mtu:        not exposed by the SDK; stays at -1 (UI shows "—")
 *   - maxPacket:  not directly observable through the SDK callback API;
 *                 stays at 0 (UI shows "—"). The SDK has already parsed the
 *                 packet for us, so the raw byte length is hidden.
 *   - maxAccl:    THE one to watch. Computed as (# fingers with valid Point3
 *                 in any DataType.Device sample) × 3 axes. 15 = full success.
 */
data class DeviceState(
    val conn: ConnectionUi = ConnectionUi.Idle,
    val mtu: Int = -1,
    val maxPacket: Int = 0,
    val maxAccl: Int = 0,
    val packetCount: Int = 0,
)

sealed interface ConnectionUi {
    data object Idle : ConnectionUi
    data class Connecting(val mac: String) : ConnectionUi
    data class Connected(val mac: String, val mtu: Int) : ConnectionUi
    data class Failed(val reason: String) : ConnectionUi
}

private fun TapSdkClient.Connection.toUi(): ConnectionUi = when (this) {
    is TapSdkClient.Connection.Idle -> ConnectionUi.Idle
    is TapSdkClient.Connection.Connecting -> ConnectionUi.Connecting(mac)
    is TapSdkClient.Connection.Connected -> ConnectionUi.Connected(mac, mtu = -1)
    is TapSdkClient.Connection.Failed -> ConnectionUi.Failed(reason)
}

private fun TapStrapClient.Connection.toUi(): ConnectionUi = when (this) {
    is TapStrapClient.Connection.Idle -> ConnectionUi.Idle
    is TapStrapClient.Connection.Scanning -> ConnectionUi.Connecting("(scanning)")
    is TapStrapClient.Connection.Connecting -> ConnectionUi.Connecting(mac)
    is TapStrapClient.Connection.Connected -> ConnectionUi.Connected(mac, mtu)
    is TapStrapClient.Connection.Failed -> ConnectionUi.Failed(reason)
}

/**
 * Now wired to the HAND-ROLLED [TapStrapClient] again. Rationale:
 * the official SDK never requests a larger MTU and its parser drops 5-finger
 * frames at the default 20-byte notification size. The hand-rolled client
 * requests MTU 517 + CONNECTION_PRIORITY_HIGH. Critically, the Tap is now
 * BONDED in system Bluetooth — earlier MTU=23 results were all on UNbonded
 * links, and many BLE peripherals only grant a larger MTU over an encrypted
 * (bonded) connection. This is the untested variable.
 */
@HiltViewModel
class DeviceViewModel @Inject constructor(
    private val client: TapStrapClient,
) : ViewModel() {

    private val _state = MutableStateFlow(DeviceState())
    val state: StateFlow<DeviceState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            client.conn.collect { c ->
                _state.update { st ->
                    val mtu = (c as? TapStrapClient.Connection.Connected)?.mtu ?: st.mtu
                    st.copy(conn = c.toUi(), mtu = mtu)
                }
            }
        }
        viewModelScope.launch {
            client.maxAcclChannels.collect { n ->
                _state.update { it.copy(maxAccl = n) }
            }
        }
        viewModelScope.launch {
            client.packetCount.collect { n ->
                _state.update { it.copy(packetCount = n) }
            }
        }
    }

    fun scan() {
        _state.update { it.copy(maxPacket = 0, maxAccl = 0, packetCount = 0) }
        client.scanAndConnect()
    }

    fun disconnect() = client.disconnect()
}
