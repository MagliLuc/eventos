package ar.eventosba.ui.sources

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.CreationExtras
import ar.eventosba.data.prefs.SourcePreferences
import ar.eventosba.data.repository.EventRepository
import ar.eventosba.di.AppContainer
import ar.eventosba.domain.model.EventSource
import ar.eventosba.domain.model.SourceStatus
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** Una fuente con el interruptor que le puso el usuario. */
data class SourceRow(
    val source: EventSource,
    val enabled: Boolean,
)

data class SourcesUiState(
    val rows: List<SourceRow> = emptyList(),
    val loaded: Boolean = false,
) {
    val allDisabled: Boolean get() = rows.isNotEmpty() && rows.none { it.enabled }

    /** Cuántas fuentes necesitan que alguien las mire. */
    val needAttention: Int
        get() = rows.count {
            it.source.status == SourceStatus.ERROR ||
                it.source.status == SourceStatus.INCOMPLETA
        }

    val visibleEvents: Int get() = rows.filter { it.enabled }.sumOf { it.source.events }
}

class SourcesViewModel(
    repository: EventRepository,
    private val prefs: SourcePreferences,
) : ViewModel() {

    val uiState: StateFlow<SourcesUiState> =
        combine(repository.observeSources(), prefs.disabledIds) { sources, disabled ->
            SourcesUiState(
                // Primero lo que necesita atención: si algo se rompió, tiene
                // que estar arriba y no perdido entre las que andan bien.
                rows = sources
                    .map { SourceRow(it, enabled = it.id !in disabled) }
                    .sortedWith(
                        compareBy({ it.source.status.prioridad }, { it.source.name.lowercase() }),
                    ),
                loaded = true,
            )
        }.stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5_000),
            initialValue = SourcesUiState(),
        )

    fun setEnabled(sourceId: String, enabled: Boolean) {
        viewModelScope.launch { prefs.setEnabled(sourceId, enabled) }
    }

    fun enableAll() {
        viewModelScope.launch { prefs.enableAll() }
    }

    companion object {
        val Factory: ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(
                modelClass: Class<T>,
                extras: CreationExtras,
            ): T {
                val app = checkNotNull(
                    extras[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY],
                )
                val container = AppContainer.from(app)
                return SourcesViewModel(
                    container.eventRepository,
                    container.sourcePreferences,
                ) as T
            }
        }
    }
}

/**
 * Lo que necesita atención va arriba.
 *
 * El `ordinal` del enum no sirve: OK es 0 y quedaría primero, justo al revés
 * de lo que hace útil un panel de diagnóstico.
 */
private val SourceStatus.prioridad: Int
    get() = when (this) {
        SourceStatus.ERROR -> 0
        SourceStatus.INCOMPLETA -> 1
        else -> 2
    }
