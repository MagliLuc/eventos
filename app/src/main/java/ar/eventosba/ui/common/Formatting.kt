package ar.eventosba.ui.common

import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

private val ES_AR = Locale("es", "AR")
private val dayFormatter = DateTimeFormatter.ofPattern("EEEE d 'de' MMMM", ES_AR)
private val shortFormatter = DateTimeFormatter.ofPattern("EEE d MMM", ES_AR)

/** "hoy" / "mañana" / "sábado 30 de agosto": el encabezado de cada grupo. */
fun LocalDate.friendlyLabel(today: LocalDate = LocalDate.now()): String = when (this) {
    today -> "Hoy"
    today.plusDays(1) -> "Mañana"
    else -> format(dayFormatter).replaceFirstChar { it.uppercase() }
}

fun LocalDate.shortLabel(today: LocalDate = LocalDate.now()): String = when (this) {
    today -> "Hoy"
    today.plusDays(1) -> "Mañana"
    else -> format(shortFormatter).replaceFirstChar { it.uppercase() }
}
