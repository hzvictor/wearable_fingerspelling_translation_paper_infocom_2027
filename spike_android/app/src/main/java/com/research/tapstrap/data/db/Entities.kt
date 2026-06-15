package com.research.tapstrap.data.db

import androidx.room.Entity
import androidx.room.ForeignKey
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(tableName = "subjects")
data class SubjectEntity(
    @PrimaryKey val id: String,
    val displayName: String,
    val dominantHand: String,        // "L" or "R"
    val handLengthCm: Float?,
    val ageRange: String?,
    val gender: String?,
    val notes: String?,
    val consentAt: Long?,
    val createdAt: Long,
    val updatedAt: Long,
)

@Entity(tableName = "protocols")
data class ProtocolEntity(
    @PrimaryKey val id: String,
    val name: String,
    val type: String,                // "gesture" | "word"
    val builtin: Boolean,
    val description: String?,
    val createdAt: Long,
)

@Entity(
    tableName = "trial_defs",
    foreignKeys = [ForeignKey(
        entity = ProtocolEntity::class,
        parentColumns = ["id"],
        childColumns = ["protocolId"],
        onDelete = ForeignKey.CASCADE,
    )],
    indices = [Index("protocolId")]
)
data class TrialDefEntity(
    @PrimaryKey val id: String,
    val protocolId: String,
    val orderIndex: Int,
    val prompt: String,
    val expectedLetters: String,
    val hint: String?,
    val group: String?,
    val confusionTest: String?,
    val estimatedDurationMs: Long,
)

@Entity(
    tableName = "sessions",
    foreignKeys = [
        ForeignKey(SubjectEntity::class, ["id"], ["subjectId"], onDelete = ForeignKey.RESTRICT),
        ForeignKey(ProtocolEntity::class, ["id"], ["protocolId"], onDelete = ForeignKey.RESTRICT),
    ],
    indices = [Index("subjectId"), Index("protocolId")]
)
data class SessionEntity(
    @PrimaryKey val id: String,
    val subjectId: String,
    val protocolId: String,
    val deviceMac: String,
    val deviceFwVersion: String?,
    val negotiatedMtu: Int,
    val maxAcclChannelsSeen: Int,
    val targetTrialsCount: Int,
    val startedAt: Long,
    val endedAt: Long?,
    val completed: Boolean,
    val notes: String?,
)

@Entity(
    tableName = "recordings",
    foreignKeys = [
        ForeignKey(SessionEntity::class, ["id"], ["sessionId"], onDelete = ForeignKey.CASCADE),
        ForeignKey(TrialDefEntity::class, ["id"], ["trialId"], onDelete = ForeignKey.RESTRICT),
    ],
    indices = [Index("sessionId"), Index("trialId")]
)
data class RecordingEntity(
    @PrimaryKey val id: String,
    val sessionId: String,
    val trialId: String,
    val orderInSession: Int,
    val imuJsonPath: String,
    val videoMp4Path: String?,
    val startedAt: Long,
    val endedAt: Long,
    val packetCount: Int,
    val acclPacketCount: Int,
    val imuPacketCount: Int,
    val maxAcclChannelsThisTrial: Int,
    val accepted: Boolean,
    val redoCount: Int,
    val signalNote: String?,
)
