package com.research.tapstrap.ui.screens.session.setup

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavHostController
import com.research.tapstrap.data.ble.TapStrapClient
import com.research.tapstrap.data.db.ProtocolDao
import com.research.tapstrap.data.db.ProtocolEntity
import com.research.tapstrap.data.db.SessionDao
import com.research.tapstrap.data.db.SessionEntity
import com.research.tapstrap.data.db.SubjectDao
import com.research.tapstrap.data.db.SubjectEntity
import com.research.tapstrap.data.db.TrialDefEntity
import com.research.tapstrap.ui.nav.Routes
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject
import java.util.UUID

data class SessionSetupState(
    val subjects: List<SubjectEntity> = emptyList(),
    val protocols: List<ProtocolEntity> = emptyList(),
    val selectedSubjectId: String? = null,
    val selectedProtocolId: String? = null,
    val trialsInSelected: List<TrialDefEntity> = emptyList(),
    val recordVideo: Boolean = true,
    val ttsEnabled: Boolean = true,
    val beepEnabled: Boolean = true,
    val deviceConn: TapStrapClient.Connection = TapStrapClient.Connection.Idle,
    val maxAcclChannels: Int = 0,
    val creating: Boolean = false,
) {
    val selectedSubject: SubjectEntity? get() = subjects.firstOrNull { it.id == selectedSubjectId }
    val selectedProtocol: ProtocolEntity? get() = protocols.firstOrNull { it.id == selectedProtocolId }
    val estimatedDurationMin: Int
        get() {
            val perTrialOverheadMs = 4_000L  // PREP + CONFIRM beats
            val total = trialsInSelected.sumOf { it.estimatedDurationMs + perTrialOverheadMs }
            return ((total / 60_000L).coerceAtLeast(1)).toInt()
        }
    val canStart: Boolean
        get() = selectedSubjectId != null &&
            selectedProtocolId != null &&
            trialsInSelected.isNotEmpty() &&
            deviceConn is TapStrapClient.Connection.Connected &&
            !creating
}

@HiltViewModel
class SessionSetupViewModel @Inject constructor(
    private val subjectDao: SubjectDao,
    private val protocolDao: ProtocolDao,
    private val sessionDao: SessionDao,
    private val client: TapStrapClient,
) : ViewModel() {

    private val _selectedSubject = MutableStateFlow<String?>(null)
    private val _selectedProtocol = MutableStateFlow<String?>(null)
    private val _trials = MutableStateFlow<List<TrialDefEntity>>(emptyList())
    private val _options = MutableStateFlow(Triple(true, true, true))  // video, tts, beep
    private val _creating = MutableStateFlow(false)

    val state: StateFlow<SessionSetupState> = combine(
        combine(subjectDao.observeAll(), protocolDao.observeAll(), _selectedSubject, _selectedProtocol, _trials) {
            subjs, protos, ssel, psel, trials -> arrayOf(subjs, protos, ssel, psel, trials)
        },
        combine(_options, client.conn, client.maxAcclChannels, _creating) { opts, conn, ch, creating ->
            arrayOf(opts, conn, ch, creating)
        }
    ) { a, b ->
        @Suppress("UNCHECKED_CAST")
        SessionSetupState(
            subjects = a[0] as List<SubjectEntity>,
            protocols = a[1] as List<ProtocolEntity>,
            selectedSubjectId = a[2] as String?,
            selectedProtocolId = a[3] as String?,
            trialsInSelected = a[4] as List<TrialDefEntity>,
            recordVideo = (b[0] as Triple<Boolean, Boolean, Boolean>).first,
            ttsEnabled = (b[0] as Triple<Boolean, Boolean, Boolean>).second,
            beepEnabled = (b[0] as Triple<Boolean, Boolean, Boolean>).third,
            deviceConn = b[1] as TapStrapClient.Connection,
            maxAcclChannels = b[2] as Int,
            creating = b[3] as Boolean,
        )
    }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), SessionSetupState())

    fun selectSubject(id: String?) { _selectedSubject.value = id }
    fun selectProtocol(id: String?) {
        _selectedProtocol.value = id
        viewModelScope.launch {
            _trials.value = id?.let { protocolDao.trialsForProtocol(it) }.orEmpty()
        }
    }
    fun setVideo(b: Boolean) = _options.update { it.copy(first = b) }
    fun setTts(b: Boolean) = _options.update { it.copy(second = b) }
    fun setBeep(b: Boolean) = _options.update { it.copy(third = b) }

    fun startSession(onStarted: (sessionId: String) -> Unit) {
        val s = state.value
        if (!s.canStart) return
        _creating.value = true
        viewModelScope.launch {
            val now = System.currentTimeMillis()
            val mac = (s.deviceConn as? TapStrapClient.Connection.Connected)?.mac ?: ""
            val mtu = (s.deviceConn as? TapStrapClient.Connection.Connected)?.mtu ?: 0
            val sessionId = java.text.SimpleDateFormat(
                "yyyyMMdd_HHmmss",
                java.util.Locale.US,
            ).format(java.util.Date(now)) + "_" + UUID.randomUUID().toString().take(4)
            val entity = SessionEntity(
                id = sessionId,
                subjectId = s.selectedSubjectId!!,
                protocolId = s.selectedProtocolId!!,
                deviceMac = mac,
                deviceFwVersion = null,
                negotiatedMtu = mtu,
                maxAcclChannelsSeen = s.maxAcclChannels,
                targetTrialsCount = s.trialsInSelected.size,
                startedAt = now,
                endedAt = null,
                completed = false,
                notes = null,
            )
            sessionDao.upsert(entity)
            _creating.value = false
            onStarted(sessionId)
        }
    }
}

private fun <A, B, C> Triple<A, B, C>.copy(
    first: A = this.first,
    second: B = this.second,
    third: C = this.third,
) = Triple(first, second, third)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SessionSetupScreen(nav: NavHostController, vm: SessionSetupViewModel = hiltViewModel()) {
    val state by vm.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("New Session") },
                navigationIcon = {
                    IconButton(onClick = { nav.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Subject picker
            DropdownField(
                label = "Subject *",
                value = state.selectedSubject?.let { "${it.id} · ${it.displayName} (${it.dominantHand})" },
                options = state.subjects.map { it.id to "${it.id} · ${it.displayName} (${it.dominantHand})" },
                onPick = vm::selectSubject,
                emptyHint = "No subjects yet — add one first."
            )

            // Protocol picker
            DropdownField(
                label = "Protocol *",
                value = state.selectedProtocol?.let { "${it.name} (${state.trialsInSelected.size} trials)" },
                options = state.protocols.map { it.id to it.name },
                onPick = vm::selectProtocol,
                emptyHint = "No protocols seeded."
            )

            // Options
            Card {
                Column(Modifier.padding(16.dp)) {
                    Text("Options", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    SwitchRow("Record video (back camera)", state.recordVideo, vm::setVideo)
                    SwitchRow("TTS read prompt aloud", state.ttsEnabled, vm::setTts)
                    SwitchRow("Beep on countdown", state.beepEnabled, vm::setBeep)
                }
            }

            // Summary
            if (state.trialsInSelected.isNotEmpty()) {
                Text(
                    "Will run ${state.trialsInSelected.size} trials · ~${state.estimatedDurationMin} min",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            // Device status line
            DeviceStatusLine(state.deviceConn, state.maxAcclChannels)

            Spacer(Modifier.weight(1f, fill = false))

            Button(
                onClick = {
                    vm.startSession { sessionId ->
                        // Navigate to Collect screen — placeholder route until Phase 3 Collect impl
                        nav.navigate("collect/$sessionId") {
                            popUpTo(Routes.SESSION_SETUP) { inclusive = true }
                        }
                    }
                },
                modifier = Modifier.fillMaxWidth().height(56.dp),
                enabled = state.canStart,
            ) {
                Icon(Icons.Filled.PlayArrow, null)
                Spacer(Modifier.width(8.dp))
                Text("Start Session")
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DropdownField(
    label: String,
    value: String?,
    options: List<Pair<String, String>>,
    onPick: (String?) -> Unit,
    emptyHint: String,
) {
    var expanded by remember { mutableStateOf(false) }
    if (options.isEmpty()) {
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
            Column(Modifier.padding(12.dp)) {
                Text(label, style = MaterialTheme.typography.labelMedium)
                Text(emptyHint, style = MaterialTheme.typography.bodySmall)
            }
        }
        return
    }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = !expanded }) {
        OutlinedTextField(
            value = value ?: "",
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.fillMaxWidth().menuAnchor(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { (id, label) ->
                DropdownMenuItem(text = { Text(label) }, onClick = { onPick(id); expanded = false })
            }
        }
    }
}

@Composable
private fun SwitchRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
        Text(label, modifier = Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@Composable
private fun DeviceStatusLine(conn: TapStrapClient.Connection, maxChannels: Int) {
    val (text, color) = when (conn) {
        is TapStrapClient.Connection.Connected ->
            "Device: ✓ Connected · MTU ${conn.mtu}" +
                (if (maxChannels > 0) " · $maxChannels channels" else "") to MaterialTheme.colorScheme.primary
        else -> "Device: ✗ Not connected — connect Tap Strap before starting" to MaterialTheme.colorScheme.error
    }
    Text(text, style = MaterialTheme.typography.bodySmall, color = color)
}
