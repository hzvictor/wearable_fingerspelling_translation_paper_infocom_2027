package com.research.tapstrap.ui.screens.subjects

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import com.research.tapstrap.data.db.SubjectEntity
import com.research.tapstrap.ui.nav.Routes

// ============================================================================
// SUBJECT LIST
// ============================================================================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SubjectListScreen(nav: NavHostController, vm: SubjectListViewModel = hiltViewModel()) {
    val subjects by vm.subjects.collectAsState()
    var pendingDelete by remember { mutableStateOf<SubjectEntity?>(null) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Subjects") },
                navigationIcon = {
                    IconButton(onClick = { nav.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, "Back")
                    }
                }
            )
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { nav.navigate(Routes.SUBJECT_NEW) },
                icon = { Icon(Icons.Filled.Add, null) },
                text = { Text("New") }
            )
        }
    ) { padding ->
        if (subjects.isEmpty()) {
            EmptyState(
                modifier = Modifier.padding(padding),
                icon = Icons.Filled.Person,
                title = "No subjects yet",
                body = "Add your first participant before starting a session.",
                ctaLabel = "+ Add subject",
                onCta = { nav.navigate(Routes.SUBJECT_NEW) }
            )
        } else {
            LazyColumn(
                modifier = Modifier
                    .padding(padding)
                    .padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(vertical = 12.dp)
            ) {
                items(subjects, key = { it.id }) { s ->
                    SubjectRow(
                        s = s,
                        onClick = { nav.navigate(Routes.subjectEdit(s.id)) },
                        onLongPress = { pendingDelete = s }
                    )
                }
            }
        }
    }

    pendingDelete?.let { s ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("Delete ${s.displayName}?") },
            text = { Text("This removes the subject. Past sessions for this subject are kept (unlinked).") },
            confirmButton = {
                TextButton(onClick = {
                    vm.delete(s); pendingDelete = null
                }) { Text("Delete") }
            },
            dismissButton = {
                TextButton(onClick = { pendingDelete = null }) { Text("Cancel") }
            }
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SubjectRow(s: SubjectEntity, onClick: () -> Unit, onLongPress: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        onClick = onClick
    ) {
        Row(
            modifier = Modifier
                .padding(16.dp)
                .fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        s.id,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        s.displayName,
                        style = MaterialTheme.typography.titleMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                Text(
                    "Dominant hand: ${if (s.dominantHand == "L") "Left" else "Right"}" +
                        (s.handLengthCm?.let { " · $it cm" } ?: ""),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (s.consentAt == null) {
                    Text(
                        "⚠ Consent not recorded",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }
            }
            TextButton(onClick = onLongPress) {
                Icon(Icons.Filled.Delete, "Delete", tint = MaterialTheme.colorScheme.error)
            }
        }
    }
}

// ============================================================================
// SUBJECT EDITOR
// ============================================================================

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SubjectEditorScreen(
    nav: NavHostController,
    id: String?,
    vm: SubjectEditorViewModel = hiltViewModel()
) {
    LaunchedEffect(id) { vm.load(id) }
    val state by vm.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (id == null) "New Subject" else "Edit Subject") },
                navigationIcon = {
                    IconButton(onClick = { nav.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, "Back")
                    }
                },
                actions = {
                    TextButton(
                        onClick = {
                            vm.save { nav.popBackStack() }
                        },
                        enabled = state.canSave
                    ) { Text(if (id == null) "Create" else "Save") }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            OutlinedTextField(
                value = state.id,
                onValueChange = vm::setId,
                label = { Text("ID *") },
                singleLine = true,
                enabled = id == null,
                supportingText = { if (id == null) Text("e.g. S001, S002, ...") },
                modifier = Modifier.fillMaxWidth()
            )

            OutlinedTextField(
                value = state.displayName,
                onValueChange = vm::setName,
                label = { Text("Display Name *") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            Text("Dominant Hand *", style = MaterialTheme.typography.labelLarge)
            Row {
                listOf("L" to "Left", "R" to "Right").forEach { (v, label) ->
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.padding(end = 16.dp)
                    ) {
                        RadioButton(selected = state.dominantHand == v, onClick = { vm.setHand(v) })
                        Text(label)
                    }
                }
            }

            OutlinedTextField(
                value = state.handLengthCm,
                onValueChange = vm::setHandLength,
                label = { Text("Hand Length (cm)") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )

            DropdownPicker(
                label = "Age Range",
                value = state.ageRange,
                options = listOf("<18", "18-29", "30-39", "40-49", "50-59", "60+", "Prefer not to say"),
                onPick = vm::setAgeRange
            )

            DropdownPicker(
                label = "Gender",
                value = state.gender,
                options = listOf("Male", "Female", "Non-binary", "Prefer not to say", "Other"),
                onPick = vm::setGender
            )

            OutlinedTextField(
                value = state.notes,
                onValueChange = vm::setNotes,
                label = { Text("Notes") },
                maxLines = 4,
                modifier = Modifier.fillMaxWidth().heightIn(min = 100.dp)
            )

            // Consent
            Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
                Column(Modifier.padding(16.dp)) {
                    Text("Consent", style = MaterialTheme.typography.titleSmall)
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "By collecting your hand-motion data, we will train and evaluate an " +
                            "American Sign Language recognition model. Data is stored locally on this " +
                            "device and shared with the research team only. You can withdraw consent at " +
                            "any time. [PLACEHOLDER — replace with IRB-approved text]",
                        style = MaterialTheme.typography.bodySmall
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(
                            checked = state.consentChecked,
                            onCheckedChange = vm::setConsent,
                            enabled = state.consentAt == null
                        )
                        Text(
                            if (state.consentAt != null)
                                "Consented at ${formatTime(state.consentAt!!)}"
                            else
                                "Subject has read and accepted the consent form"
                        )
                    }
                }
            }

            state.error?.let { err ->
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                    Text(err, modifier = Modifier.padding(12.dp))
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DropdownPicker(
    label: String,
    value: String?,
    options: List<String>,
    onPick: (String?) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = !expanded }
    ) {
        OutlinedTextField(
            value = value ?: "",
            onValueChange = {},
            readOnly = true,
            label = { Text(label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded) },
            modifier = Modifier.fillMaxWidth().menuAnchor()
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(text = { Text("— none —") }, onClick = { onPick(null); expanded = false })
            options.forEach { opt ->
                DropdownMenuItem(text = { Text(opt) }, onClick = { onPick(opt); expanded = false })
            }
        }
    }
}

@Composable
internal fun EmptyState(
    modifier: Modifier = Modifier,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    body: String,
    ctaLabel: String? = null,
    onCta: (() -> Unit)? = null,
) {
    Column(
        modifier = modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(icon, null, modifier = Modifier.size(64.dp), tint = MaterialTheme.colorScheme.outline)
        Spacer(Modifier.height(16.dp))
        Text(title, style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(8.dp))
        Text(body, style = MaterialTheme.typography.bodyMedium)
        if (ctaLabel != null && onCta != null) {
            Spacer(Modifier.height(24.dp))
            Button(onClick = onCta) { Text(ctaLabel) }
        }
    }
}

private fun formatTime(ms: Long): String {
    val d = java.util.Date(ms)
    return java.text.SimpleDateFormat("yyyy-MM-dd HH:mm", java.util.Locale.US).format(d)
}
