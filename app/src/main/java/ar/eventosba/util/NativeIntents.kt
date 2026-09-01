package ar.eventosba.util

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.CalendarContract
import android.widget.Toast
import ar.eventosba.R
import ar.eventosba.domain.model.Event
import java.time.LocalTime
import java.time.ZoneId

/**
 * Integraciones nativas de costo cero.
 *
 * En vez de un SDK de calendario o de mapas (que implican cuota, API key o
 * tarjeta), delegamos en las apps que el usuario ya tiene: el sistema resuelve
 * el Intent y nosotros no pagamos ni pedimos permisos.
 */
object NativeIntents {

    private val BUENOS_AIRES: ZoneId = ZoneId.of("America/Argentina/Buenos_Aires")

    /**
     * Abre el compositor de eventos del calendario nativo.
     *
     * `ACTION_INSERT` sobre `CalendarContract.Events.CONTENT_URI` no requiere
     * los permisos READ/WRITE_CALENDAR: el usuario ve el borrador y confirma.
     */
    fun addToCalendar(context: Context, event: Event) {
        val zone = BUENOS_AIRES
        val start = event.date
            .atTime(event.startTime ?: LocalTime.of(9, 0))
            .atZone(zone)
            .toInstant()
            .toEpochMilli()

        // Sin hora de fin publicada asumimos 2 h, que es la duracion tipica
        // de estas actividades y evita un evento de duracion cero.
        val end = event.endTime
            ?.let { event.date.atTime(it).atZone(zone).toInstant().toEpochMilli() }
            ?: (start + DEFAULT_DURATION_MILLIS)

        val intent = Intent(Intent.ACTION_INSERT).apply {
            data = CalendarContract.Events.CONTENT_URI
            putExtra(CalendarContract.Events.TITLE, event.title)
            putExtra(CalendarContract.Events.EVENT_LOCATION, event.venue.locationLine())
            putExtra(CalendarContract.Events.DESCRIPTION, event.calendarDescription())
            putExtra(CalendarContract.EXTRA_EVENT_BEGIN_TIME, start)
            putExtra(CalendarContract.EXTRA_EVENT_END_TIME, end)
            putExtra(CalendarContract.Events.ALL_DAY, event.startTime == null)
            putExtra(CalendarContract.Events.EVENT_TIMEZONE, zone.id)
            putExtra(CalendarContract.Events.ACCESS_LEVEL, CalendarContract.Events.ACCESS_DEFAULT)
        }
        context.launch(intent, R.string.no_calendar_app)
    }

    /**
     * Abre la app de mapas por defecto (Google Maps, OsmAnd, Waze, Organic Maps…).
     *
     * El esquema `geo:` es del sistema operativo, no de un proveedor: funciona
     * con cualquiera que el usuario tenga y no consume cuota de ninguna API.
     */
    fun openDirections(context: Context, event: Event) {
        val venue = event.venue
        val label = Uri.encode("${venue.name}, ${venue.fullAddress}")
        val uri = if (venue.hasCoordinates) {
            // Coordenadas + label: la app de mapas pone el pin exacto y muestra
            // el nombre de la sede.
            Uri.parse("geo:${venue.lat},${venue.lon}?q=${venue.lat},${venue.lon}($label)")
        } else {
            Uri.parse("geo:0,0?q=$label")
        }
        context.launch(Intent(Intent.ACTION_VIEW, uri), R.string.no_maps_app)
    }

    /** Abre una URL (reserva o ficha oficial) en el navegador del usuario. */
    fun openUrl(context: Context, url: String) {
        context.launch(Intent(Intent.ACTION_VIEW, Uri.parse(url)), R.string.no_browser_app)
    }

    /** Comparte el evento por cualquier app instalada (WhatsApp, mail, etc.). */
    fun share(context: Context, event: Event) {
        val text = buildString {
            appendLine(event.title)
            append(event.date)
            event.timeLabel?.let { append(" · $it") }
            appendLine()
            appendLine(event.venue.locationLine())
            appendLine(event.accessMode.label)
            event.sourceUrl?.let { appendLine(it) }
        }
        val intent = Intent.createChooser(
            Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_SUBJECT, event.title)
                putExtra(Intent.EXTRA_TEXT, text.trim())
            },
            null,
        )
        context.launch(intent, R.string.no_browser_app)
    }

    private const val DEFAULT_DURATION_MILLIS = 2 * 60 * 60 * 1000L

    /**
     * Lanza el Intent avisando por Toast si no hay ninguna app que lo resuelva.
     *
     * Se atrapa `ActivityNotFoundException` en lugar de consultar
     * `resolveActivity`: en Android 11+ ese chequeo depende del bloque
     * `<queries>` del manifest y devuelve null de mas.
     */
    private fun Context.launch(intent: Intent, errorRes: Int) {
        try {
            startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, errorRes, Toast.LENGTH_SHORT).show()
        }
    }
}

// La cola sale de la zona, no de una constante: con la agenda ampliada al
// AMBA, un ", CABA" fijo mandaba a la app de mapas a la calle homonima de
// Capital para cualquier evento del Conurbano.
private fun ar.eventosba.domain.model.Venue.locationLine(): String =
    (listOfNotNull(name, address, neighborhood).distinct() + zone.locality)
        .joinToString(", ")

private fun Event.calendarDescription(): String = buildString {
    description?.let { appendLine(it) }
    appendLine()
    appendLine("Modalidad: ${accessMode.label}")
    reservationUrl?.let { appendLine("Reservas: $it") }
    sourceUrl?.let { appendLine("Fuente: $it") }
    append("Agregado desde Agenda Gratis BA")
}
