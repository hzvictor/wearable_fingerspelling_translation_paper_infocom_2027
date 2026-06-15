package com.research.tapstrap

import android.app.Application
import com.research.tapstrap.data.seed.ProtocolSeeder
import dagger.hilt.android.HiltAndroidApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltAndroidApp
class TapStrapApp : Application() {
    @Inject lateinit var seeder: ProtocolSeeder

    private val appScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        appScope.launch { seeder.seedIfMissing() }
    }
}
