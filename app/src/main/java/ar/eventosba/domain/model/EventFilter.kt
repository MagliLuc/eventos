package ar.eventosba.domain.model

import java.time.LocalDate

/**
 * Estado de filtrado de la home. Se aplica en memoria sobre la lista ya
 * cacheada: no hay round-trip a la red ni consultas SQL por cada tecla.
 */
data class EventFilter(
    val query: String = "",
    val categories: Set<Category> = emptySet(),
    val neighborhoods: Set<String> = emptySet(),
    val timeSlots: Set<TimeSlot> = emptySet(),
    val accessModes: Set<AccessMode> = emptySet(),
    val date: LocalDate? = null,
    val onlyFavorites: Boolean = false,
) {
    val activeCount: Int
        get() = categories.size + neighborhoods.size + timeSlots.size +
            accessModes.size + (if (date != null) 1 else 0)

    val isEmpty: Boolean get() = activeCount == 0 && query.isBlank() && !onlyFavorites

    fun matches(event: Event): Boolean =
        event.matchesQuery(query) &&
            (categories.isEmpty() || event.category in categories) &&
            (neighborhoods.isEmpty() || event.venue.neighborhood in neighborhoods) &&
            (timeSlots.isEmpty() || event.timeSlot in timeSlots) &&
            (accessModes.isEmpty() || event.accessMode in accessModes) &&
            (date == null || event.date == date) &&
            (!onlyFavorites || event.isFavorite)

    fun toggleCategory(value: Category) =
        copy(categories = categories.toggle(value))

    fun toggleNeighborhood(value: String) =
        copy(neighborhoods = neighborhoods.toggle(value))

    fun toggleTimeSlot(value: TimeSlot) =
        copy(timeSlots = timeSlots.toggle(value))

    fun toggleAccessMode(value: AccessMode) =
        copy(accessModes = accessModes.toggle(value))

    fun cleared() = EventFilter(query = query, onlyFavorites = onlyFavorites)
}

private fun <T> Set<T>.toggle(value: T): Set<T> =
    if (value in this) this - value else this + value
