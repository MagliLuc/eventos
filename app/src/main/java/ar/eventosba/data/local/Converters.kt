package ar.eventosba.data.local

import androidx.room.TypeConverter
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeParseException

/**
 * Conversores de Room. Guardamos fechas y horas como texto ISO (`2026-08-30`,
 * `19:00`) para que la base sea legible y ordenable con `ORDER BY` sin
 * conversiones.
 */
class Converters {

    @TypeConverter
    fun dateToString(value: LocalDate?): String? = value?.toString()

    @TypeConverter
    fun stringToDate(value: String?): LocalDate? = value?.let {
        runCatching { LocalDate.parse(it) }.getOrNull()
    }

    @TypeConverter
    fun timeToString(value: LocalTime?): String? = value?.toString()

    @TypeConverter
    fun stringToTime(value: String?): LocalTime? = value?.let {
        try {
            LocalTime.parse(it)
        } catch (_: DateTimeParseException) {
            null
        }
    }

    @TypeConverter
    fun tagsToString(value: List<String>?): String = value.orEmpty().joinToString("|")

    @TypeConverter
    fun stringToTags(value: String?): List<String> =
        value?.split("|")?.filter { it.isNotBlank() }.orEmpty()
}
