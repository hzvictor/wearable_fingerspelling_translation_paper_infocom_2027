package com.research.tapstrap

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.research.tapstrap.ui.nav.TapStrapNavHost
import com.research.tapstrap.ui.theme.TapStrapTheme
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { AppRoot() }
    }
}

@Composable
private fun AppRoot() {
    TapStrapTheme {
        Surface(modifier = Modifier.fillMaxSize()) {
            TapStrapNavHost()
        }
    }
}
