package com.research.tapstrap.data.seed

import android.content.Context
import com.research.tapstrap.data.db.ProtocolDao
import com.research.tapstrap.data.db.ProtocolEntity
import com.research.tapstrap.data.db.TrialDefEntity
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * Seeds the built-in ASL protocol library into Room on first launch.
 * Source JSON files live in assets/builtin_protocols/, generated from
 * the Mac collect_*.py codebase by scripts/export_builtin_protocols.py.
 */
class ProtocolSeeder(
    private val context: Context,
    private val dao: ProtocolDao,
) {

    @Serializable
    private data class TrialJson(
        val id: String,
        val orderIndex: Int,
        val prompt: String,
        val expectedLetters: String,
        val hint: String? = null,
        val group: String? = null,
        val confusionTest: String? = null,
        val estimatedDurationMs: Long,
    )

    @Serializable
    private data class ProtocolJson(
        val id: String,
        val name: String,
        val type: String,
        val builtin: Boolean = true,
        val description: String? = null,
        val trials: List<TrialJson>,
    )

    private val json = Json { ignoreUnknownKeys = true }

    private val builtinFiles = listOf(
        "asl_alphabet.json",
        "asl_digits.json",
        "confusion_words.json",
        "all_words.json",
    )

    suspend fun seedIfMissing() {
        val now = System.currentTimeMillis()
        for (file in builtinFiles) {
            val raw = context.assets.open("builtin_protocols/$file")
                .bufferedReader().use { it.readText() }
            val proto: ProtocolJson = json.decodeFromString(raw)

            // Skip if already in DB and unchanged
            val existing = dao.byId(proto.id)
            if (existing != null) continue

            val protoEntity = ProtocolEntity(
                id = proto.id,
                name = proto.name,
                type = proto.type,
                builtin = true,
                description = proto.description,
                createdAt = now,
            )
            val trialEntities = proto.trials.mapIndexed { i, t ->
                TrialDefEntity(
                    id = t.id,
                    protocolId = proto.id,
                    orderIndex = t.orderIndex,
                    prompt = t.prompt,
                    expectedLetters = t.expectedLetters,
                    hint = t.hint,
                    group = t.group,
                    confusionTest = t.confusionTest,
                    estimatedDurationMs = t.estimatedDurationMs,
                )
            }
            dao.replaceProtocolWithTrials(protoEntity, trialEntities)
        }
    }
}
