package com.research.tapstrap.di

import android.content.Context
import androidx.room.Room
import com.research.tapstrap.data.db.AppDatabase
import com.research.tapstrap.data.db.ProtocolDao
import com.research.tapstrap.data.db.RecordingDao
import com.research.tapstrap.data.db.SessionDao
import com.research.tapstrap.data.db.SubjectDao
import com.research.tapstrap.data.seed.ProtocolSeeder
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides @Singleton
    fun provideDb(@ApplicationContext ctx: Context): AppDatabase =
        Room.databaseBuilder(ctx, AppDatabase::class.java, "tapstrap.db").build()

    @Provides fun subjectDao(db: AppDatabase): SubjectDao = db.subjectDao()
    @Provides fun protocolDao(db: AppDatabase): ProtocolDao = db.protocolDao()
    @Provides fun sessionDao(db: AppDatabase): SessionDao = db.sessionDao()
    @Provides fun recordingDao(db: AppDatabase): RecordingDao = db.recordingDao()

    @Provides @Singleton
    fun provideSeeder(@ApplicationContext ctx: Context, dao: ProtocolDao): ProtocolSeeder =
        ProtocolSeeder(ctx, dao)
}
