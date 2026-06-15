package com.research.tapstrap.ui.screens.home

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.BluetoothConnected
import androidx.compose.material.icons.filled.BluetoothDisabled
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Group
import androidx.compose.material.icons.filled.ListAlt
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import com.research.tapstrap.data.ble.TapStrapClient
import com.research.tapstrap.ui.nav.Routes

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(nav: NavHostController, vm: HomeViewModel = hiltViewModel()) {
    val state by vm.state.collectAsState()
    Scaffold(
        topBar = { TopAppBar(title = { Text("TapStrap Collector") }) }
    ) { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .padding(16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            DeviceStatusCard(
                conn = state.conn,
                maxAcclChannels = state.maxAcclChannels,
                packetCount = state.packetCount,
                onClick = { nav.navigate(Routes.DEVICE) }
            )
            CountCard(Icons.Filled.Group, "Subjects", state.subjectCount) { nav.navigate(Routes.SUBJECTS) }
            CountCard(Icons.Filled.ListAlt, "Protocols", state.protocolCount) { nav.navigate(Routes.PROTOCOLS) }
            CountCard(Icons.Filled.PlayArrow, "Sessions", state.sessionCount) { nav.navigate(Routes.SESSIONS) }

            Spacer(Modifier.height(8.dp))

            Button(
                onClick = { nav.navigate(Routes.SESSION_SETUP) },
                modifier = Modifier.fillMaxWidth().height(64.dp),
                enabled = state.canStartSession,
            ) {
                Icon(Icons.Filled.PlayArrow, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Start New Session", style = MaterialTheme.typography.titleMedium)
            }
            if (!state.canStartSession) {
                Text(
                    blocker(state),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.padding(horizontal = 8.dp)
                )
            }

            TextButton(onClick = { nav.navigate(Routes.SETTINGS) }) {
                Icon(Icons.Filled.Settings, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("Settings")
            }
        }
    }
}

private fun blocker(s: HomeState): String {
    val reasons = mutableListOf<String>()
    if (s.conn !is TapStrapClient.Connection.Connected) reasons += "connect Tap Strap"
    if (s.subjectCount == 0) reasons += "add a subject"
    if (s.protocolCount == 0) reasons += "import a protocol"
    return "To start: " + reasons.joinToString(" + ")
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DeviceStatusCard(
    conn: TapStrapClient.Connection,
    maxAcclChannels: Int,
    packetCount: Int,
    onClick: () -> Unit,
) {
    val connected = conn is TapStrapClient.Connection.Connected
    val tone = when (conn) {
        is TapStrapClient.Connection.Connected -> MaterialTheme.colorScheme.primaryContainer
        is TapStrapClient.Connection.Failed -> MaterialTheme.colorScheme.errorContainer
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    val icon = when (conn) {
        is TapStrapClient.Connection.Connected -> Icons.Filled.BluetoothConnected
        is TapStrapClient.Connection.Failed -> Icons.Filled.BluetoothDisabled
        else -> Icons.Filled.Bluetooth
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = tone),
        onClick = onClick,
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(icon, contentDescription = null)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text("Device", style = MaterialTheme.typography.labelMedium)
                    Text(
                        when (conn) {
                            TapStrapClient.Connection.Idle -> "Not connected"
                            TapStrapClient.Connection.Scanning -> "Scanning..."
                            is TapStrapClient.Connection.Connecting -> "Connecting..."
                            is TapStrapClient.Connection.Connected -> "Connected"
                            is TapStrapClient.Connection.Failed -> "Failed"
                        },
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        when (conn) {
                            TapStrapClient.Connection.Idle -> "Tap to connect Tap Strap"
                            TapStrapClient.Connection.Scanning -> "Looking for Tap Strap…"
                            is TapStrapClient.Connection.Connecting -> conn.mac
                            is TapStrapClient.Connection.Connected -> "${conn.mac} · MTU ${conn.mtu}"
                            is TapStrapClient.Connection.Failed -> conn.reason
                        },
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }

            // Channel pill — the critical 5-finger breakthrough indicator
            if (connected || maxAcclChannels > 0) {
                Spacer(Modifier.height(12.dp))
                ChannelPill(maxAcclChannels, packetCount)
            }
        }
    }
}

@Composable
private fun ChannelPill(maxChannels: Int, packetCount: Int) {
    val (bgColor, fgColor, icon, label) = when {
        maxChannels >= 15 -> Quartet(
            Color(0xFF1B5E20),       // dark green
            Color.White,
            Icons.Filled.CheckCircle,
            "5-FINGER OK · 15 channels"
        )
        maxChannels in 1..14 -> Quartet(
            Color(0xFFB71C1C),       // dark red
            Color.White,
            Icons.Filled.Warning,
            "Truncated · only $maxChannels ch (firmware cap)"
        )
        else -> Quartet(
            Color(0x33000000),
            Color.Black,
            Icons.Filled.Bluetooth,
            "Awaiting packets…"
        )
    }
    Surface(
        color = bgColor,
        shape = RoundedCornerShape(20.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(icon, contentDescription = null, tint = fgColor)
            Spacer(Modifier.width(8.dp))
            Text(
                label,
                color = fgColor,
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.weight(1f),
            )
            if (packetCount > 0) {
                Text(
                    "$packetCount pkts",
                    color = fgColor.copy(alpha = 0.8f),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
        }
    }
}

private data class Quartet(
    val bg: Color,
    val fg: Color,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
    val label: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CountCard(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    count: Int,
    onClick: () -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth(), onClick = onClick) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(icon, contentDescription = null)
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
            }
            Text("$count", style = MaterialTheme.typography.headlineMedium)
        }
    }
}
