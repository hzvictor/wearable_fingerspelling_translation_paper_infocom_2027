package com.research.tapstrap.ui.screens.protocols

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.ListAlt
import androidx.compose.material.icons.filled.Lock
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
import com.research.tapstrap.data.db.ProtocolDao
import com.research.tapstrap.data.db.ProtocolEntity
import com.research.tapstrap.data.db.TrialDefEntity
import com.research.tapstrap.ui.nav.Routes
import com.research.tapstrap.ui.screens.subjects.EmptyState
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

// ============================================================================
// PROTOCOL LIST
// ============================================================================

@HiltViewModel
class ProtocolListViewModel @Inject constructor(
    private val dao: ProtocolDao,
) : ViewModel() {
    val protocols: StateFlow<List<ProtocolEntity>> =
        dao.observeAll().stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProtocolListScreen(nav: NavHostController, vm: ProtocolListViewModel = hiltViewModel()) {
    val protocols by vm.protocols.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Protocols") },
                navigationIcon = {
                    IconButton(onClick = { nav.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, "Back")
                    }
                }
            )
        }
    ) { padding ->
        if (protocols.isEmpty()) {
            EmptyState(
                modifier = Modifier.padding(padding),
                icon = Icons.Filled.ListAlt,
                title = "Loading built-in protocols…",
                body = "Restart the app if this persists.",
            )
        } else {
            val builtin = protocols.filter { it.builtin }
            val custom = protocols.filter { !it.builtin }
            LazyColumn(
                modifier = Modifier.padding(padding).padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                if (builtin.isNotEmpty()) {
                    item { SectionHeader("Built-in") }
                    items(builtin, key = { it.id }) { p ->
                        ProtocolRow(p, onClick = { nav.navigate(Routes.protocolEdit(p.id)) })
                    }
                }
                if (custom.isNotEmpty()) {
                    item { SectionHeader("Custom") }
                    items(custom, key = { it.id }) { p ->
                        ProtocolRow(p, onClick = { nav.navigate(Routes.protocolEdit(p.id)) })
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.Bold,
        modifier = Modifier.padding(vertical = 8.dp),
        color = MaterialTheme.colorScheme.primary
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ProtocolRow(p: ProtocolEntity, onClick: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth(), onClick = onClick) {
        Row(
            modifier = Modifier.padding(16.dp).fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            if (p.builtin) Icon(Icons.Filled.Lock, null, modifier = Modifier.size(20.dp))
            else Icon(Icons.Filled.ListAlt, null, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(p.name, style = MaterialTheme.typography.titleMedium)
                Text(
                    "${p.type} · ${if (p.builtin) "built-in" else "custom"}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                p.description?.let {
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

// ============================================================================
// PROTOCOL EDITOR (read-only view for builtin; trial list shown)
// ============================================================================

data class ProtocolEditorState(
    val protocol: ProtocolEntity? = null,
    val trials: List<TrialDefEntity> = emptyList(),
    val loading: Boolean = true,
)

@HiltViewModel
class ProtocolEditorViewModel @Inject constructor(
    private val dao: ProtocolDao,
) : ViewModel() {
    private val _state = MutableStateFlow(ProtocolEditorState())
    val state: StateFlow<ProtocolEditorState> = _state.asStateFlow()

    fun load(id: String?) {
        if (id == null) {
            _state.value = ProtocolEditorState(loading = false)
            return
        }
        viewModelScope.launch {
            val p = dao.byId(id)
            val ts = if (p != null) dao.trialsForProtocol(id) else emptyList()
            _state.value = ProtocolEditorState(p, ts, loading = false)
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProtocolEditorScreen(
    nav: NavHostController,
    id: String?,
    vm: ProtocolEditorViewModel = hiltViewModel()
) {
    LaunchedEffect(id) { vm.load(id) }
    val state by vm.state.collectAsState()
    val title = state.protocol?.name ?: if (id == null) "New Protocol" else "Protocol"

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title) },
                navigationIcon = {
                    IconButton(onClick = { nav.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, "Back")
                    }
                }
            )
        }
    ) { padding ->
        if (state.loading) {
            Box(Modifier.padding(padding).fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }
        val p = state.protocol
        if (p == null) {
            EmptyState(
                modifier = Modifier.padding(padding),
                icon = Icons.Filled.ListAlt,
                title = "Custom protocol editor",
                body = "Custom protocol creation is coming in Phase 4. Use built-in protocols for now.",
            )
            return@Scaffold
        }
        Column(Modifier.padding(padding).padding(16.dp)) {
            if (p.builtin) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Lock, null)
                        Spacer(Modifier.width(8.dp))
                        Text("Read-only built-in protocol")
                    }
                }
                Spacer(Modifier.height(12.dp))
            }
            p.description?.let {
                Text(it, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(12.dp))
            }
            Text(
                "Trials (${state.trials.size})",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.height(8.dp))
            LazyColumn(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                items(state.trials, key = { it.id }) { t ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier.padding(12.dp).fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                "${t.orderIndex + 1}.",
                                modifier = Modifier.width(36.dp),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                            Column(Modifier.weight(1f)) {
                                Text(t.prompt, style = MaterialTheme.typography.titleMedium)
                                if (t.expectedLetters != t.prompt) {
                                    Text(
                                        "→ ${t.expectedLetters}",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                                t.hint?.let {
                                    Text(
                                        it,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                            t.group?.let {
                                AssistChip(onClick = {}, label = { Text(it) })
                            }
                        }
                    }
                }
            }
        }
    }
}
