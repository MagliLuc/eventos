package ar.eventosba.ui.home

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.CreationExtras
import ar.eventosba.data.repository.EventRepository
import ar.eventosba.di.AppContainer
import ar.eventosba.domain.model.AccessMode
import ar.eventosba.domain.model.Category
import ar.eventosba.domain.model.Event
import ar.eventosba.domain.model.EventFilter
import ar.eventosba.domain.model.TimeSlot
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate

data class HomeUiState(
    val events: List<Event> = emptyList(),
    val allEvents: List<Event> = emptyList(),
    val filter: EventFilter = EventFilter(),
    val isRefreshing: Boolean = false,
    val errorMessage: String? = null,
    val lastSyncMillis: Long? = null,
) {
    /** Barrios presentes en la agenda actual: los chips no se inventan. */
    val availableNeighborhoods: List<String>
        get() = allEvents.mapNotNull { it.venue.neighborhood }.distinct().sorted()

    val availableDates: List<LocalDate>
        get() = allEvents.map { it.date }.distinct().sorted()

    /** Cuenta por categoria, para mostrar cuantos eventos hay detras de cada chip. */
    val countByCategory: Map<Category, Int>
        get() = allEvents.groupingBy { it.category }.eachCount()

    val isEmpty: Boolean get() = events.isEmpty()
    val hasNoDataAtAll: Boolean get() = allEvents.isEmpty()
}

class HomeViewModel(
    application: Application,
    private val repository: EventRepository,
) : AndroidViewModel(application) {

    private val filter = MutableStateFlow(EventFilter())
    private val refreshing = MutableStateFlow(false)
    private val error = MutableStateFlow<String?>(null)

    val uiState: StateFlow<HomeUiState> = combine(
        repository.observeUpcoming(),
        filter,
        refreshing,
        error,
        repository.lastSyncMillis,
    ) { events, activeFilter, isRefreshing, errorMessage, lastSync ->
        HomeUiState(
            // El filtrado ocurre en memoria sobre la lista ya cacheada: es
            // instantaneo mientras el usuario tipea y no toca la red.
            events = events.filter(activeFilter::matches),
            allEvents = events,
            filter = activeFilter,
            isRefreshing = isRefreshing,
            errorMessage = errorMessage,
            lastSyncMillis = lastSync,
        )
    }.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = HomeUiState(),
    )

    init {
        refresh()
    }

    fun refresh() {
        if (refreshing.value) return
        viewModelScope.launch {
            refreshing.value = true
            error.value = null
            repository.refresh().onFailure {
                // Sin conexion no es un estado de error de la pantalla: la
                // lista cacheada se sigue viendo y solo avisamos arriba.
                error.value = "No pudimos actualizar la agenda. Mostrando la última descarga."
            }
            refreshing.value = false
        }
    }

    fun onQueryChange(value: String) = filter.update { it.copy(query = value) }
    fun onCategoryToggle(value: Category) = filter.update { it.toggleCategory(value) }
    fun onNeighborhoodToggle(value: String) = filter.update { it.toggleNeighborhood(value) }
    fun onTimeSlotToggle(value: TimeSlot) = filter.update { it.toggleTimeSlot(value) }
    fun onAccessModeToggle(value: AccessMode) = filter.update { it.toggleAccessMode(value) }
    fun onDateSelect(value: LocalDate?) = filter.update { it.copy(date = value) }
    fun onFavoritesToggle() = filter.update { it.copy(onlyFavorites = !it.onlyFavorites) }
    fun clearFilters() = filter.update { it.cleared() }
    fun dismissError() { error.value = null }

    fun toggleFavorite(eventId: String) {
        viewModelScope.launch { repository.toggleFavorite(eventId) }
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
                return HomeViewModel(app, AppContainer.from(app).eventRepository) as T
            }
        }
    }
}
