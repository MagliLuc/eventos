package ar.eventosba.data.local

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.PrimaryKey
import ar.eventosba.domain.model.EventSource
import ar.eventosba.domain.model.SourceStatus

/**
 * Estado de una fuente, cacheado igual que los eventos.
 *
 * Va a Room y no en memoria porque el panel tiene que funcionar sin conexión,
 * que es la premisa de toda la app: si el teléfono está en el subte, la lista
 * se ve y el panel también.
 */
@Entity(tableName = "sources")
data class SourceEntity(
    @PrimaryKey val id: String,
    val name: String,
    val url: String?,
    val status: String,
    val detail: String,
    val events: Int,
    @ColumnInfo(name = "items_read") val itemsRead: Int,
)

fun SourceEntity.toDomain(): EventSource = EventSource(
    id = id,
    name = name,
    url = url,
    status = SourceStatus.fromRaw(status),
    detail = detail,
    events = events,
    itemsRead = itemsRead,
)
