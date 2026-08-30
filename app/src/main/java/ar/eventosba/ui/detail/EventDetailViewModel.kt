package ar.eventosba.ui.detail

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.createSavedStateHandle
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.CreationExtras
import ar.eventosba.data.repository.EventRepository
import ar.eventosba.di.AppContainer
import ar.eventosba.domain.model.Event
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class EventDetailViewModel(
    application: Application,
    private val repository: EventRepository,
    private val eventId: String,
) : AndroidViewModel(application) {

    val event: StateFlow<Event?> = repository.observeEvent(eventId)
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)

    fun toggleFavorite() {
        viewModelScope.launch { repository.toggleFavorite(eventId) }
    }

    companion object {
        const val ARG_EVENT_ID = "eventId"

        val Factory: ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(
                modelClass: Class<T>,
                extras: CreationExtras,
            ): T {
                val app = checkNotNull(
                    extras[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY],
                )
                val handle: SavedStateHandle = extras.createSavedStateHandle()
                val id = checkNotNull(handle.get<String>(ARG_EVENT_ID)) {
                    "Falta el argumento $ARG_EVENT_ID en la ruta de navegación"
                }
                return EventDetailViewModel(
                    app,
                    AppContainer.from(app).eventRepository,
                    id,
                ) as T
            }
        }
    }
}
