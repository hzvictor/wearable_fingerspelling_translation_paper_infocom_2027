package com.research.tapstrap.data.db

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface SubjectDao {
    @Query("SELECT * FROM subjects ORDER BY updatedAt DESC") fun observeAll(): Flow<List<SubjectEntity>>
    @Query("SELECT * FROM subjects WHERE id = :id") suspend fun byId(id: String): SubjectEntity?
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(s: SubjectEntity)
    @Delete suspend fun delete(s: SubjectEntity)
    @Query("SELECT COUNT(*) FROM subjects") fun count(): Flow<Int>
}

@Dao
interface ProtocolDao {
    @Query("SELECT * FROM protocols ORDER BY builtin DESC, name ASC")
    fun observeAll(): Flow<List<ProtocolEntity>>
    @Query("SELECT * FROM protocols WHERE id = :id") suspend fun byId(id: String): ProtocolEntity?
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(p: ProtocolEntity)
    @Delete suspend fun delete(p: ProtocolEntity)

    @Query("SELECT * FROM trial_defs WHERE protocolId = :protocolId ORDER BY orderIndex")
    suspend fun trialsForProtocol(protocolId: String): List<TrialDefEntity>
    @Query("SELECT * FROM trial_defs WHERE protocolId = :protocolId ORDER BY orderIndex")
    fun observeTrialsForProtocol(protocolId: String): Flow<List<TrialDefEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsertTrials(trials: List<TrialDefEntity>)
    @Query("DELETE FROM trial_defs WHERE protocolId = :protocolId")
    suspend fun deleteTrialsForProtocol(protocolId: String)

    @Transaction
    suspend fun replaceProtocolWithTrials(p: ProtocolEntity, trials: List<TrialDefEntity>) {
        upsert(p)
        deleteTrialsForProtocol(p.id)
        upsertTrials(trials)
    }

    @Query("SELECT COUNT(*) FROM protocols") fun count(): Flow<Int>
}

@Dao
interface SessionDao {
    @Query("SELECT * FROM sessions ORDER BY startedAt DESC")
    fun observeAll(): Flow<List<SessionEntity>>
    @Query("SELECT * FROM sessions WHERE id = :id") suspend fun byId(id: String): SessionEntity?
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(s: SessionEntity)
    @Update suspend fun update(s: SessionEntity)
    @Delete suspend fun delete(s: SessionEntity)
    @Query("SELECT COUNT(*) FROM sessions") fun count(): Flow<Int>
    @Query("SELECT * FROM sessions WHERE subjectId = :subjectId ORDER BY startedAt DESC")
    fun observeBySubject(subjectId: String): Flow<List<SessionEntity>>
}

@Dao
interface RecordingDao {
    @Query("SELECT * FROM recordings WHERE sessionId = :sessionId ORDER BY orderInSession")
    fun observeBySession(sessionId: String): Flow<List<RecordingEntity>>
    @Insert(onConflict = OnConflictStrategy.REPLACE) suspend fun upsert(r: RecordingEntity)
    @Update suspend fun update(r: RecordingEntity)
}
