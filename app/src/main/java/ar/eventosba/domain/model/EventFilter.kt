package ar.eventosba.domain.model

import java.time.DayOfWeek
import java.time.LocalDate

/**
 * Rangos rapidos de fecha.
 *
 * Con una ventana de 21 dias, un chip por dia serian 21 chips ilegibles. La
 * gente no piensa "18 de septiembre", piensa "hoy", "mañana", "el finde".
 */
enum class DateRangeFilter(val label: String) {
    TODAS("Cualquier día"),
    HOY("Hoy"),
    MANANA("Mañana"),
    FIN_DE_SEMANA("Fin de semana"),
    PROXIMOS_7("Próximos 7 días");

    fun matches(date: LocalDate, today: LocalDate = LocalDate.now()): Boolean = when (this) {
        TODAS -> true
        HOY -> date == today
        MANANA -> date == today.plusDays(1)
        // El finde que viene, y si hoy ya es sábado o domingo, este.
        FIN_DE_SEMANA -> date in today.weekendRange()
        PROXIMOS_7 -> !date.isBefore(today) && date.isBefore(today.plusDays(8))
    }
}

private fun LocalDate.weekendRange(): ClosedRange<LocalDate> {
    val saturday = when (dayOfWeek) {
        DayOfWeek.SATURDAY -> this
        DayOfWeek.SUNDAY -> minusDays(1)
        else -> plusDays((DayOfWeek.SATURDAY.value - dayOfWeek.value).toLong())
    }
    return saturday..saturday.plusDays(1)
}

/** Criterios de ordenamiento disponibles en la home. */
enum class SortOrder(val label: String) {
    FECHA_ASC("Próximos primero"),
    FECHA_DESC("Más lejanos primero"),
    TITULO("Alfabético");

    /** El agrupado por día solo tiene sentido si el orden es cronológico. */
    val groupsByDay: Boolean get() = this != TITULO

    fun comparator(): Comparator<Event> = when (this) {
        FECHA_ASC -> compareBy<Event> { it.date }
            // Los eventos sin horario van al final del día, no al principio.
            .thenBy { it.startTime == null }
            .thenBy { it.startTime }
            .thenBy { it.title }
        FECHA_DESC -> compareByDescending<Event> { it.date }
            .thenBy { it.startTime == null }
            .thenBy { it.startTime }
            .thenBy { it.title }
        TITULO -> compareBy({ it.title.lowercase() }, { it.date })
    }
}

/**
 * Estado de filtrado y ordenamiento de la home. Se aplica en memoria sobre la
 * lista ya cacheada: no hay round-trip a la red ni consultas SQL por tecla.
 */
data class EventFilter(
    val query: String = "",
    val categories: Set<Category> = emptySet(),
    val neighborhoods: Set<String> = emptySet(),
    val timeSlots: Set<TimeSlot> = emptySet(),
    val accessModes: Set<AccessMode> = emptySet(),
    val dateRange: DateRangeFilter = DateRangeFilter.TODAS,
    val sortOrder: SortOrder = SortOrder.FECHA_ASC,
    val onlyFavorites: Boolean = false,
    /**
     * Fuentes que el usuario apago en el panel.
     *
     * Se guardan las apagadas y no las encendidas: asi un evento cuya fuente
     * la app no conoce -- por ejemplo uno que quedo cacheado de un feed
     * anterior -- se sigue viendo. Ocultarlo por no estar en una lista de
     * permitidos seria hacerlo desaparecer sin que nadie lo haya pedido.
     */
    val disabledSources: Set<String> = emptySet(),
) {
    /** Cuántos filtros hay puestos. El orden no cuenta: no descarta nada. */
    val activeCount: Int
        get() = categories.size + neighborhoods.size + timeSlots.size +
            accessModes.size + (if (dateRange != DateRangeFilter.TODAS) 1 else 0)

    val isEmpty: Boolean get() = activeCount == 0 && query.isBlank() && !onlyFavorites

    fun matches(event: Event, today: LocalDate = LocalDate.now()): Boolean =
        event.matchesQuery(query) &&
            (categories.isEmpty() || event.category in categories) &&
            (neighborhoods.isEmpty() || event.venue.neighborhood in neighborhoods) &&
            (timeSlots.isEmpty() || event.timeSlot in timeSlots) &&
            (accessModes.isEmpty() || event.accessMode in accessModes) &&
            dateRange.matches(event.date, today) &&
            (!onlyFavorites || event.isFavorite) &&
            (event.sourceId == null || event.sourceId !in disabledSources)

    /** Filtra y ordena en un solo paso. */
    fun apply(events: List<Event>, today: LocalDate = LocalDate.now()): List<Event> =
        events.filter { matches(it, today) }.sortedWith(sortOrder.comparator())

    fun toggleCategory(value: Category) = copy(categories = categories.toggle(value))
    fun toggleNeighborhood(value: String) = copy(neighborhoods = neighborhoods.toggle(value))
    fun toggleTimeSlot(value: TimeSlot) = copy(timeSlots = timeSlots.toggle(value))
    fun toggleAccessMode(value: AccessMode) = copy(accessModes = accessModes.toggle(value))

    /** Volver a tocar el rango activo lo desactiva. */
    fun toggleDateRange(value: DateRangeFilter) =
        copy(dateRange = if (dateRange == value) DateRangeFilter.TODAS else value)

    /**
     * Limpiar borra los filtros de la home, no la busqueda, el orden, los
     * guardados ni las fuentes apagadas: esas ultimas se manejan en su propio
     * panel y borrarlas desde aca seria una sorpresa.
     */
    fun cleared() = EventFilter(
        query = query,
        sortOrder = sortOrder,
        onlyFavorites = onlyFavorites,
        disabledSources = disabledSources,
    )
}

private fun <T> Set<T>.toggle(value: T): Set<T> =
    if (value in this) this - value else this + value
