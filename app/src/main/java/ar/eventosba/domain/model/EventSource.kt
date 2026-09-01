package ar.eventosba.domain.model

/**
 * Una fuente de la agenda y cómo le fue en la última corrida del scraper.
 *
 * El estado lo calcula el scraper, no la app: ahí están los números (cuántas
 * fichas leyó, por qué descartó cada una) y ahí vive el criterio. La app lo
 * muestra. Si mañana cambia la regla, cambia en un solo lado.
 */
data class EventSource(
    val id: String,
    val name: String,
    val url: String?,
    val status: SourceStatus,
    /** Una línea en castellano explicando el estado, escrita por el scraper. */
    val detail: String,
    val events: Int,
    val itemsRead: Int,
)

/**
 * Los cuatro estados. La distinción que importa es entre los dos del medio:
 *
 * - [INCOMPLETA] es un problema **nuestro**: la fuente publica actividades que
 *   no logramos leer.
 * - [SIN_EVENTOS] es el resultado **correcto**: la fuente anda y hoy no tiene
 *   nada gratuito. El Teatro Colón vende entradas; que devuelva cero no es una
 *   falla que haya que ir a arreglar.
 *
 * Mostrarlas iguales haría perder tiempo en lo que funciona, o ignorar lo que
 * se rompió.
 */
enum class SourceStatus(val label: String, val shortLabel: String) {
    OK("Funcionando", "OK"),
    INCOMPLETA("Trae datos incompletos", "Incompleta"),
    SIN_EVENTOS("Sin eventos gratuitos ahora", "Sin eventos"),
    ERROR("Con problemas", "Error"),

    /** El feed trajo un estado que esta versión de la app no conoce. */
    DESCONOCIDA("Estado desconocido", "?");

    companion object {
        /** Tolerante a estados nuevos del feed: cae en DESCONOCIDA sin crashear. */
        fun fromRaw(raw: String?): SourceStatus =
            entries.firstOrNull { it.name.equals(raw, ignoreCase = true) } ?: DESCONOCIDA
    }
}
