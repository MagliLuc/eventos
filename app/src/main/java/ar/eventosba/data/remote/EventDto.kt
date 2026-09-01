package ar.eventosba.data.remote

import ar.eventosba.data.local.EventEntity
import ar.eventosba.data.local.SourceEntity
import ar.eventosba.data.local.VenueEmbedded
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.LocalDate
import java.time.LocalTime

/**
 * Espejo exacto de `docs/events.json`. Es la unica capa que conoce el formato
 * del feed; si el JSON cambia, se toca aca y nada mas.
 */
@Serializable
data class EventsFeedDto(
    @SerialName("schema_version") val schemaVersion: Int = 1,
    @SerialName("generated_at") val generatedAt: String? = null,
    val city: String? = null,
    val license: String? = null,
    // Un feed viejo no trae este bloque: por eso la lista vacia por defecto.
    // La app tiene que seguir andando contra el JSON que ya esta publicado.
    val sources: List<SourceDto> = emptyList(),
    val events: List<EventDto> = emptyList(),
)

@Serializable
data class SourceDto(
    val id: String,
    val name: String,
    val url: String? = null,
    val status: String = "DESCONOCIDA",
    val detail: String = "",
    val events: Int = 0,
    @SerialName("items_read") val itemsRead: Int = 0,
)

fun SourceDto.toEntity(): SourceEntity = SourceEntity(
    id = id,
    name = name.trim(),
    url = url,
    status = status.uppercase(),
    detail = detail.trim(),
    events = events,
    itemsRead = itemsRead,
)

@Serializable
data class EventDto(
    val id: String,
    val title: String,
    val description: String? = null,
    val category: String = "OTROS",
    val tags: List<String> = emptyList(),
    val date: String,
    @SerialName("start_time") val startTime: String? = null,
    @SerialName("end_time") val endTime: String? = null,
    @SerialName("all_day") val allDay: Boolean = false,
    @SerialName("access_mode") val accessMode: String = "INGRESO_LIBRE",
    @SerialName("reservation_url") val reservationUrl: String? = null,
    val venue: VenueDto,
    @SerialName("source_name") val sourceName: String? = null,
    @SerialName("source_id") val sourceId: String? = null,
    @SerialName("source_url") val sourceUrl: String? = null,
    @SerialName("image_url") val imageUrl: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
)

@Serializable
data class VenueDto(
    val id: String,
    val name: String,
    val address: String? = null,
    val neighborhood: String? = null,
    val commune: Int? = null,
    val lat: Double? = null,
    val lon: Double? = null,
)

/**
 * Mapea DTO -> entidad. Devuelve null si la fila no es utilizable (fecha
 * corrupta): preferimos descartar un evento antes que romper la sincronizacion
 * entera por un registro mal formado en el feed.
 */
fun EventDto.toEntity(): EventEntity? {
    val parsedDate = runCatching { LocalDate.parse(date) }.getOrNull() ?: return null
    return EventEntity(
        id = id,
        title = title.trim(),
        description = description?.trim(),
        category = category.uppercase(),
        tags = tags,
        date = parsedDate,
        startTime = startTime.toLocalTimeOrNull(),
        endTime = endTime.toLocalTimeOrNull(),
        accessMode = accessMode.uppercase(),
        reservationUrl = reservationUrl,
        venue = VenueEmbedded(
            id = venue.id,
            name = venue.name.trim(),
            address = venue.address,
            neighborhood = venue.neighborhood,
            commune = venue.commune,
            lat = venue.lat,
            lon = venue.lon,
        ),
        sourceName = sourceName,
        sourceUrl = sourceUrl,
        sourceId = sourceId,
        imageUrl = imageUrl,
    )
}

private fun String?.toLocalTimeOrNull(): LocalTime? =
    this?.takeIf { it.isNotBlank() }?.let { runCatching { LocalTime.parse(it) }.getOrNull() }
