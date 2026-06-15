package com.research.tapstrap.ui.screens.device

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
/* DeviceState/ConnectionUi are in this same package so no import needed */

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DeviceSetupScreen(nav: NavHostController, vm: DeviceViewModel = hiltViewModel()) {
    val state by vm.state.collectAsState()
    val ctx = LocalContext.current

    val perms: Array<String> = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
    } else {
        arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
    }

    val permLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { result -> if (result.all { it.value }) vm.scan() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Device") },
                navigationIcon = {
                    IconButton(onClick = { nav.popBackStack() }) {
                        Icon(Icons.Filled.ArrowBack, contentDescription = "Back")
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier.padding(padding).padding(16.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            ConnectionBanner(state.conn)

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        val allGranted = perms.all {
                            ContextCompat.checkSelfPermission(ctx, it) == PackageManager.PERMISSION_GRANTED
                        }
                        if (allGranted) vm.scan() else permLauncher.launch(perms)
                    },
                    modifier = Modifier.weight(1f),
                    enabled = state.conn !is ConnectionUi.Connected,
                ) { Text("Scan & Connect") }

                OutlinedButton(
                    onClick = { vm.disconnect() },
                    modifier = Modifier.weight(1f),
                    enabled = state.conn is ConnectionUi.Connected,
                ) { Text("Disconnect") }
            }

            MetricsCard(state)

            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("How to read these numbers", fontWeight = FontWeight.Bold)
                    Text("· MTU ≥ 37  ⇒  the BLE pipe can carry full 15-channel accl packets", style = MaterialTheme.typography.bodySmall)
                    Text("· Max accl channels = 15  ⇒  Android broke the 8-channel macOS ceiling", style = MaterialTheme.typography.bodySmall)
                    Text("· Max accl channels = 8   ⇒  Tap Strap firmware is the real limit", style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}

@Composable
private fun ConnectionBanner(conn: ConnectionUi) {
    val (text, color) = when (conn) {
        ConnectionUi.Idle -> "Not connected" to MaterialTheme.colorScheme.errorContainer
        is ConnectionUi.Connecting -> "Connecting: ${conn.mac}..." to MaterialTheme.colorScheme.surfaceVariant
        is ConnectionUi.Connected -> "Connected: ${conn.mac}" to MaterialTheme.colorScheme.primaryContainer
        is ConnectionUi.Failed -> "Error: ${conn.reason}" to MaterialTheme.colorScheme.errorContainer
    }
    Surface(color = color, modifier = Modifier.fillMaxWidth()) {
        Text(text, modifier = Modifier.padding(12.dp), fontWeight = FontWeight.Bold)
    }
}

@Composable
private fun MetricsCard(state: DeviceState) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("KEY METRICS", fontWeight = FontWeight.Bold)
            MetricRow("MTU", if (state.mtu < 0) "—" else "${state.mtu}", state.mtu >= 37)
            MetricRow("Max packet size", if (state.maxPacket == 0) "—" else "${state.maxPacket} B", state.maxPacket > 23)
            MetricRow("Max accl channels", if (state.maxAccl == 0) "—" else "${state.maxAccl}", state.maxAccl >= 15, big = true)
            Text("Packets received: ${state.packetCount}", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun MetricRow(label: String, value: String, good: Boolean, big: Boolean = false) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("$label:", modifier = Modifier.weight(1f))
        Text(
            value,
            fontWeight = if (big) FontWeight.Bold else FontWeight.Normal,
            style = if (big) MaterialTheme.typography.titleLarge else MaterialTheme.typography.bodyLarge,
            color = if (good) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
        )
        if (good) Text(" ✓", color = MaterialTheme.colorScheme.primary)
    }
}
