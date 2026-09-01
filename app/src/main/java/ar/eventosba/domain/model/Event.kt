package ar.eventosba.domain.model

import java.time.LocalDate
import java.time.LocalTime

/**
 * Un evento cultural gratuito, tal como lo consume la UI.
 *
 * Es el modelo de dominio: no tiene anotaciones de Room ni de serializacion,
 * asi que un cambio en el feed o en la base no se filtra a las pantallas.
 */
data class Event(
    val id: String,
    val title: String,
    val description: String?,
    val category: Category,
    val tags: List<String>,
    val date: LocalDate,
    val startTime: LocalTime?,
    val endTime: LocalTime?,
    val accessMode: AccessMode,
    val reservationUrl: String?,
    val venue: Venue,
    val sourceName: String?,
    val sourceUrl: String?,
    /**
     * Quien produjo el evento, aparte del nombre que se muestra.
     *
     * Hacen falta los dos: la agenda curada publica eventos con el
     * `sourceName` de la sede ("Centro Cultural Recoleta"), igual que la
     * fuente en vivo homonima. Sin este id, apagar una en el panel apagaria
     * las dos.
     */
    val sourceId: String?,
    val imageUrl: String?,
    val isFavorite: Boolean = false,
) {
    /** Franja horaria, para el filtro rapido de la home. */
    val timeSlot: TimeSlot get() = TimeSlot.of(startTime)

    /** "14:00 a 17:00", "18:00" o null si la agenda no publico horario. */
    val timeLabel: String?
        get() = when {
            startTime == null -> null
            endTime == null -> startTime.toString()
            else -> "$startTime a $endTime"
        }

    fun matchesQuery(query: String): Boolean {
        if (query.isBlank()) return true
        val needle = query.trim().lowercase()
        return title.lowercase().contains(needle) ||
            venue.name.lowercase().contains(needle) ||
            venue.neighborhood?.lowercase()?.contains(needle) == true ||
            tags.any { it.lowercase().contains(needle) }
    }
}

data class Venue(
    val id: String,
    val name: String,
    val address: String?,
    val neighborhood: String?,
    val commune: Int?,
    val lat: Double?,
    val lon: Double?,
) {
    val hasCoordinates: Boolean get() = lat != null && lon != null

    /** Direccion legible para el Intent de mapas y para la ficha. */
    val fullAddress: String
        get() = listOfNotNull(address, neighborhood, "CABA").joinToString(", ")
}

enum class Category(val label: String) {
    MUSICA("Música"),
    ARTES_VISUALES("Artes visuales"),
    CINE("Cine"),
    TEATRO("Teatro y danza"),
    INFANTILES("Infantiles"),
    FERIAS("Ferias y aire libre"),
    OTROS("Otros");

    companion object {
        /** Tolerante a categorias nuevas del feed: cae en OTROS en vez de crashear. */
        fun fromRaw(raw: String?): Category =
            entries.firstOrNull { it.name.equals(raw, ignoreCase = true) } ?: OTROS
    }
}

enum class AccessMode(val label: String, val shortLabel: String) {
    INGRESO_LIBRE("Ingreso libre", "Libre"),
    ORDEN_DE_LLEGADA("Por orden de llegada", "Por llegada"),
    RESERVA_PREVIA("Requiere reserva previa", "Reserva");

    companion object {
        fun fromRaw(raw: String?): AccessMode =
            entries.firstOrNull { it.name.equals(raw, ignoreCase = true) } ?: INGRESO_LIBRE
    }
}

enum class TimeSlot(val label: String) {
    MANANA("Mañana"),
    TARDE("Tarde"),
    NOCHE("Noche"),
    SIN_HORARIO("Sin horario");

    companion object {
        fun of(time: LocalTime?): TimeSlot = when {
            time == null -> SIN_HORARIO
            time.hour < 13 -> MANANA
            time.hour < 19 -> TARDE
            else -> NOCHE
        }
    }
}
