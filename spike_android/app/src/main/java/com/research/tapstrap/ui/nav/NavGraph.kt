package com.research.tapstrap.ui.nav

import androidx.compose.runtime.Composable
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.research.tapstrap.ui.screens.device.DeviceSetupScreen
import com.research.tapstrap.ui.screens.home.HomeScreen
import com.research.tapstrap.ui.screens.library.SessionListScreen
import com.research.tapstrap.ui.screens.protocols.ProtocolEditorScreen
import com.research.tapstrap.ui.screens.protocols.ProtocolListScreen
import com.research.tapstrap.ui.screens.session.setup.SessionSetupScreen
import com.research.tapstrap.ui.screens.settings.SettingsScreen
import com.research.tapstrap.ui.screens.subjects.SubjectEditorScreen
import com.research.tapstrap.ui.screens.subjects.SubjectListScreen

object Routes {
    const val HOME = "home"
    const val DEVICE = "device"
    const val SUBJECTS = "subjects"
    const val SUBJECT_NEW = "subject/new"
    const val SUBJECT_EDIT = "subject/{id}"
    fun subjectEdit(id: String) = "subject/$id"
    const val PROTOCOLS = "protocols"
    const val PROTOCOL_NEW = "protocol/new"
    const val PROTOCOL_EDIT = "protocol/{id}"
    fun protocolEdit(id: String) = "protocol/$id"
    const val SESSION_SETUP = "session/setup"
    const val SESSIONS = "sessions"
    const val SETTINGS = "settings"
}

@Composable
fun TapStrapNavHost(navController: NavHostController = rememberNavController()) {
    NavHost(navController = navController, startDestination = Routes.HOME) {
        composable(Routes.HOME) { HomeScreen(nav = navController) }
        composable(Routes.DEVICE) { DeviceSetupScreen(nav = navController) }

        composable(Routes.SUBJECTS) { SubjectListScreen(nav = navController) }
        composable(Routes.SUBJECT_NEW) { SubjectEditorScreen(nav = navController, id = null) }
        composable(Routes.SUBJECT_EDIT) { back ->
            SubjectEditorScreen(nav = navController, id = back.arguments?.getString("id"))
        }

        composable(Routes.PROTOCOLS) { ProtocolListScreen(nav = navController) }
        composable(Routes.PROTOCOL_NEW) { ProtocolEditorScreen(nav = navController, id = null) }
        composable(Routes.PROTOCOL_EDIT) { back ->
            ProtocolEditorScreen(nav = navController, id = back.arguments?.getString("id"))
        }

        composable(Routes.SESSION_SETUP) { SessionSetupScreen(nav = navController) }
        composable(Routes.SESSIONS) { SessionListScreen(nav = navController) }
        composable(Routes.SETTINGS) { SettingsScreen(nav = navController) }
    }
}
