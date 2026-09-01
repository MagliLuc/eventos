package ar.eventosba.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters

@Database(
    entities = [EventEntity::class, FavoriteEntity::class, SourceEntity::class],
    // 2: se suma `sources` y la columna source_id en `events`.
    // 3: ampliacion al AMBA -- venue_zone y contribution en `events`.
    version = 3,
    exportSchema = true,
)
@TypeConverters(Converters::class)
abstract class EventDatabase : RoomDatabase() {

    abstract fun eventDao(): EventDao

    companion object {
        private const val NAME = "eventos.db"

        @Volatile
        private var instance: EventDatabase? = null

        fun get(context: Context): EventDatabase =
            instance ?: synchronized(this) {
                instance ?: build(context.applicationContext).also { instance = it }
            }

        private fun build(context: Context): EventDatabase =
            Room.databaseBuilder(context, EventDatabase::class.java, NAME)
                // La cache se puede regenerar bajando el JSON de nuevo, asi que
                // ante un cambio de schema sin migracion preferimos recrear
                // antes que crashear. Los favoritos se pierden solo en ese caso.
                .fallbackToDestructiveMigration()
                .build()
    }
}
