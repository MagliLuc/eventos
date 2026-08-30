package ar.eventosba.data.local

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow
import java.time.LocalDate

@Dao
interface EventDao {

    /**
     * Flujo principal de la home. El `LEFT JOIN` trae el flag de favorito sin
     * una segunda consulta, y el orden viene de SQL para no reordenar en cada
     * recomposicion.
     */
    @Transaction
    @Query(
        """
        SELECT e.*, (f.event_id IS NOT NULL) AS is_favorite
        FROM events e
        LEFT JOIN favorites f ON f.event_id = e.id
        WHERE e.date >= :from
        ORDER BY e.date ASC, e.start_time IS NULL, e.start_time ASC, e.title ASC
        """,
    )
    fun observeUpcoming(from: LocalDate): Flow<List<EventWithFavorite>>

    @Transaction
    @Query(
        """
        SELECT e.*, 1 AS is_favorite
        FROM events e
        INNER JOIN favorites f ON f.event_id = e.id
        ORDER BY e.date ASC, e.start_time ASC
        """,
    )
    fun observeFavorites(): Flow<List<EventWithFavorite>>

    @Transaction
    @Query(
        """
        SELECT e.*, (f.event_id IS NOT NULL) AS is_favorite
        FROM events e
        LEFT JOIN favorites f ON f.event_id = e.id
        WHERE e.id = :id
        """,
    )
    fun observeById(id: String): Flow<EventWithFavorite?>

    @Query("SELECT COUNT(*) FROM events")
    suspend fun count(): Int

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(events: List<EventEntity>)

    @Query("DELETE FROM events WHERE id NOT IN (:keepIds)")
    suspend fun deleteNotIn(keepIds: List<String>)

    /** Poda la agenda vieja para que la base no crezca sin limite. */
    @Query("DELETE FROM events WHERE date < :before")
    suspend fun deleteBefore(before: LocalDate)

    /**
     * Reemplazo atomico: si la escritura falla a la mitad, la transaccion
     * revierte y el usuario conserva la agenda anterior completa.
     */
    @Transaction
    suspend fun replaceAll(events: List<EventEntity>, today: LocalDate) {
        upsertAll(events)
        deleteNotIn(events.map { it.id })
        deleteBefore(today)
    }

    // Sin valores por defecto en los parametros: Room genera la
    // implementacion de estos metodos y conviene no depender de los
    // bridges sinteticos de Kotlin.
    @Query("INSERT OR IGNORE INTO favorites (event_id, saved_at) VALUES (:id, :savedAt)")
    suspend fun addFavorite(id: String, savedAt: Long)

    @Query("DELETE FROM favorites WHERE event_id = :id")
    suspend fun removeFavorite(id: String)

    @Query("SELECT EXISTS(SELECT 1 FROM favorites WHERE event_id = :id)")
    suspend fun isFavorite(id: String): Boolean

    @Transaction
    suspend fun toggleFavorite(id: String) {
        if (isFavorite(id)) removeFavorite(id) else addFavorite(id, System.currentTimeMillis())
    }
}
