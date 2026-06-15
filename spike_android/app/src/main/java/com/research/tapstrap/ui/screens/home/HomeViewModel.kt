package com.research.tapstrap.ui.screens.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.research.tapstrap.data.ble.TapStrapClient
import com.research.tapstrap.data.db.ProtocolDao
import com.research.tapstrap.data.db.SessionDao
import com.research.tapstrap.data.db.SubjectDao
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

data class HomeState(
    val conn: TapStrapClient.Connection = TapStrapClient.Connection.Idle,
    val maxAcclChannels: Int = 0,
    val packetCount: Int = 0,
    val subjectCount: Int = 0,
    val protocolCount: Int = 0,
    val sessionCount: Int = 0,
) {
    val canStartSession: Boolean
        get() = conn is TapStrapClient.Connection.Connected && subjectCount > 0 && protocolCount > 0
}

private data class DeviceStatus(
    val conn: TapStrapClient.Connection,
    val maxAcclChannels: Int,
    val packetCount: Int,
)

private data class Counts(val subjects: Int, val protocols: Int, val sessions: Int)

@HiltViewModel
class HomeViewModel @Inject constructor(
    client: TapStrapClient,
    subjectDao: SubjectDao,
    protocolDao: ProtocolDao,
    sessionDao: SessionDao,
) : ViewModel() {

    private val device = combine(
        client.conn,
        client.maxAcclChannels,
        client.packetCount,
        ::DeviceStatus,
    )

    private val counts = combine(
        subjectDao.count(),
        protocolDao.count(),
        sessionDao.count(),
        ::Counts,
    )

    val state: StateFlow<HomeState> = combine(device, counts) { d, c ->
        HomeState(
            conn = d.conn,
            maxAcclChannels = d.maxAcclChannels,
            packetCount = d.packetCount,
            subjectCount = c.subjects,
            protocolCount = c.protocols,
            sessionCount = c.sessions,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), HomeState())
}
