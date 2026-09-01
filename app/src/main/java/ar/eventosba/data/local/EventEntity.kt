package ar.eventosba.data.local

import androidx.room.ColumnInfo
import androidx.room.Embedded
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey
import ar.eventosba.domain.model.AccessMode
import ar.eventosba.domain.model.Category
import ar.eventosba.domain.model.Contribution
import ar.eventosba.domain.model.Event
import ar.eventosba.domain.model.Venue
import ar.eventosba.domain.model.Zone
import java.time.LocalDate
import java.time.LocalTime

/**
 * Fila de la cache local. Es lo que hace posible el modo 100% offline:
 * la app arranca leyendo de aca y recien despues intenta refrescar.
 *
 * La sede va `@Embedded` en la misma tabla en vez de normalizada: son ~20
 * sedes repetidas, y una sola tabla evita un JOIN en cada consulta de la home.
 */
@Entity(
    tableName = "events",
    indices = [
        Index("date"),
        Index("category"),
        Index("venue_neighborhood"),
        Index("venue_zone"),
    ],
)
data class EventEntity(
    @PrimaryKey val id: String,
    val title: String,
    val description: String?,
    val category: String,
    val tags: List<String>,
    val date: LocalDate,
    @ColumnInfo(name = "start_time") val startTime: LocalTime?,
    @ColumnInfo(name = "end_time") val endTime: LocalTime?,
    @ColumnInfo(name = "access_mode") val accessMode: String,
    val contribution: String?,
    @ColumnInfo(name = "reservation_url") val reservationUrl: String?,
    @Embedded(prefix = "venue_") val venue: VenueEmbedded,
    @ColumnInfo(name = "source_name") val sourceName: String?,
    @ColumnInfo(name = "source_id") val sourceId: String?,
    @ColumnInfo(name = "source_url") val sourceUrl: String?,
    @ColumnInfo(name = "image_url") val imageUrl: String?,
)

data class VenueEmbedded(
    val id: String,
    val name: String,
    val address: String?,
    val neighborhood: String?,
    val commune: Int?,
    val lat: Double?,
    val lon: Double?,
    val zone: String = "CABA",
)

/**
 * Favoritos en tabla aparte a proposito: la sincronizacion diaria borra e
 * inserta `events`, y si el flag viviera en esa fila el usuario perderia
 * sus guardados cada mañana.
 */
@Entity(tableName = "favorites")
data class FavoriteEntity(
    @PrimaryKey @ColumnInfo(name = "event_id") val eventId: String,
    @ColumnInfo(name = "saved_at") val savedAt: Long = System.currentTimeMillis(),
)

/** Proyeccion del LEFT JOIN entre `events` y `favorites`. */
data class EventWithFavorite(
    @Embedded val event: EventEntity,
    @ColumnInfo(name = "is_favorite") val isFavorite: Boolean,
)

fun EventWithFavorite.toDomain(): Event = Event(
    id = event.id,
    title = event.title,
    description = event.description,
    category = Category.fromRaw(event.category),
    tags = event.tags,
    date = event.date,
    startTime = event.startTime,
    endTime = event.endTime,
    accessMode = AccessMode.fromRaw(event.accessMode),
    contribution = Contribution.fromRaw(event.contribution),
    reservationUrl = event.reservationUrl,
    venue = Venue(
        id = event.venue.id,
        name = event.venue.name,
        address = event.venue.address,
        neighborhood = event.venue.neighborhood,
        commune = event.venue.commune,
        lat = event.venue.lat,
        lon = event.venue.lon,
        zone = Zone.fromRaw(event.venue.zone),
    ),
    sourceName = event.sourceName,
    sourceUrl = event.sourceUrl,
    sourceId = event.sourceId,
    imageUrl = event.imageUrl,
    isFavorite = isFavorite,
)
