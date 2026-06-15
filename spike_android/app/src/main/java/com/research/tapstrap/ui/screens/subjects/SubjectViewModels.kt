package com.research.tapstrap.ui.screens.subjects

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.research.tapstrap.data.db.SubjectDao
import com.research.tapstrap.data.db.SubjectEntity
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SubjectListViewModel @Inject constructor(
    private val dao: SubjectDao,
) : ViewModel() {
    val subjects: StateFlow<List<SubjectEntity>> = dao.observeAll()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5000), emptyList())

    fun delete(s: SubjectEntity) {
        viewModelScope.launch { dao.delete(s) }
    }
}

data class SubjectEditorState(
    val id: String = "",
    val displayName: String = "",
    val dominantHand: String = "R",
    val handLengthCm: String = "",
    val ageRange: String? = null,
    val gender: String? = null,
    val notes: String = "",
    val consentChecked: Boolean = false,
    val consentAt: Long? = null,
    val error: String? = null,
    val loaded: Boolean = false,
) {
    val canSave: Boolean
        get() = id.matches(Regex("^[A-Za-z0-9_-]{1,16}$")) &&
            displayName.isNotBlank() &&
            (dominantHand == "L" || dominantHand == "R") &&
            (handLengthCm.isBlank() || handLengthCm.toFloatOrNull()?.let { it in 5f..30f } == true)
}

@HiltViewModel
class SubjectEditorViewModel @Inject constructor(
    private val dao: SubjectDao,
) : ViewModel() {

    private val _state = MutableStateFlow(SubjectEditorState())
    val state: StateFlow<SubjectEditorState> = _state.asStateFlow()
    private var existing: SubjectEntity? = null

    fun load(id: String?) {
        if (_state.value.loaded) return
        viewModelScope.launch {
            if (id == null) {
                _state.value = SubjectEditorState(id = nextId(), loaded = true)
            } else {
                val s = dao.byId(id)
                if (s != null) {
                    existing = s
                    _state.value = SubjectEditorState(
                        id = s.id,
                        displayName = s.displayName,
                        dominantHand = s.dominantHand,
                        handLengthCm = s.handLengthCm?.toString() ?: "",
                        ageRange = s.ageRange,
                        gender = s.gender,
                        notes = s.notes ?: "",
                        consentChecked = s.consentAt != null,
                        consentAt = s.consentAt,
                        loaded = true,
                    )
                } else {
                    _state.value = SubjectEditorState(id = id, loaded = true, error = "Subject not found")
                }
            }
        }
    }

    private suspend fun nextId(): String {
        // Walk S001..S999 to find the first unused. Simple, good for <1k subjects.
        for (i in 1..999) {
            val candidate = "S%03d".format(i)
            if (dao.byId(candidate) == null) return candidate
        }
        return "S" + System.currentTimeMillis().toString().takeLast(6)
    }

    fun setId(v: String) = _state.update { it.copy(id = v.trim(), error = null) }
    fun setName(v: String) = _state.update { it.copy(displayName = v, error = null) }
    fun setHand(v: String) = _state.update { it.copy(dominantHand = v) }
    fun setHandLength(v: String) = _state.update { it.copy(handLengthCm = v, error = null) }
    fun setAgeRange(v: String?) = _state.update { it.copy(ageRange = v) }
    fun setGender(v: String?) = _state.update { it.copy(gender = v) }
    fun setNotes(v: String) = _state.update { it.copy(notes = v) }
    fun setConsent(v: Boolean) = _state.update {
        it.copy(
            consentChecked = v,
            consentAt = if (v && it.consentAt == null) System.currentTimeMillis() else it.consentAt
        )
    }

    fun save(onDone: () -> Unit) {
        val s = _state.value
        if (!s.canSave) {
            _state.update { it.copy(error = "Please fill required fields correctly.") }
            return
        }
        viewModelScope.launch {
            val now = System.currentTimeMillis()
            // If ID is new, ensure uniqueness
            if (existing == null && dao.byId(s.id) != null) {
                _state.update { it.copy(error = "ID '${s.id}' is already in use.") }
                return@launch
            }
            val entity = SubjectEntity(
                id = s.id,
                displayName = s.displayName.trim(),
                dominantHand = s.dominantHand,
                handLengthCm = s.handLengthCm.toFloatOrNull(),
                ageRange = s.ageRange,
                gender = s.gender,
                notes = s.notes.ifBlank { null },
                consentAt = if (s.consentChecked) (s.consentAt ?: now) else null,
                createdAt = existing?.createdAt ?: now,
                updatedAt = now,
            )
            dao.upsert(entity)
            onDone()
        }
    }
}
