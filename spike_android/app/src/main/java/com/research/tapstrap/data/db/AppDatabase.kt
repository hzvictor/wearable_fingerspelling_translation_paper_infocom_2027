package com.research.tapstrap.data.db

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [
        SubjectEntity::class,
        ProtocolEntity::class,
        TrialDefEntity::class,
        SessionEntity::class,
        RecordingEntity::class,
    ],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun subjectDao(): SubjectDao
    abstract fun protocolDao(): ProtocolDao
    abstract fun sessionDao(): SessionDao
    abstract fun recordingDao(): RecordingDao
}
