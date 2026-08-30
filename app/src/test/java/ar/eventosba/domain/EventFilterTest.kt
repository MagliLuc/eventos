package ar.eventosba.domain

import ar.eventosba.domain.model.AccessMode
import ar.eventosba.domain.model.Category
import ar.eventosba.domain.model.Event
import ar.eventosba.domain.model.DateRangeFilter
import ar.eventosba.domain.model.EventFilter
import ar.eventosba.domain.model.SortOrder
import ar.eventosba.domain.model.TimeSlot
import ar.eventosba.domain.model.Venue
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.LocalDate
import java.time.LocalTime

/**
 * El filtrado es la funcionalidad central de la app y corre en memoria, asi
 * que se puede testear entero en la JVM: sin emulador ni red.
 */
class EventFilterTest {

    private val milonga = event(
        id = "milonga",
        title = "Gran Milonga de Cierre",
        category = Category.MUSICA,
        neighborhood = "La Boca",
        start = LocalTime.of(17, 0),
        access = AccessMode.ORDEN_DE_LLEGADA,
    )

    private val muestra = event(
        id = "muestra",
        title = "Muestra de Klemm",
        category = Category.ARTES_VISUALES,
        neighborhood = "Recoleta",
        start = LocalTime.of(13, 0),
        access = AccessMode.INGRESO_LIBRE,
    )

    private val colon = event(
        id = "colon",
        title = "Sexteto Mayor en el Colón",
        category = Category.MUSICA,
        neighborhood = "San Nicolás",
        start = LocalTime.of(20, 0),
        access = AccessMode.RESERVA_PREVIA,
    )

    private val all = listOf(milonga, muestra, colon)

    private val hoy: LocalDate = LocalDate.of(2026, 8, 30)   // domingo

    private fun apply(filter: EventFilter) = filter.apply(all, hoy).map { it.id }

    @Test
    fun `sin filtros devuelve todo, ya ordenado por hora`() {
        // Mismo día para los tres, así que manda la hora: 13:00, 17:00, 20:00.
        assertEquals(listOf("muestra", "milonga", "colon"), apply(EventFilter()))
    }

    @Test
    fun `categorias dentro de la misma faceta suman en OR`() {
        val filter = EventFilter()
            .toggleCategory(Category.MUSICA)
            .toggleCategory(Category.ARTES_VISUALES)
        assertEquals(3, apply(filter).size)
    }

    @Test
    fun `facetas distintas se combinan en AND`() {
        val filter = EventFilter()
            .toggleCategory(Category.MUSICA)
            .toggleNeighborhood("La Boca")
        assertEquals(listOf("milonga"), apply(filter))
    }

    @Test
    fun `filtra por franja horaria`() {
        assertEquals(listOf("colon"), apply(EventFilter().toggleTimeSlot(TimeSlot.NOCHE)))
        assertEquals(
            listOf("milonga", "muestra"),
            apply(EventFilter().toggleTimeSlot(TimeSlot.TARDE)).sorted(),
        )
    }

    @Test
    fun `filtra por modalidad de ingreso`() {
        val filter = EventFilter().toggleAccessMode(AccessMode.RESERVA_PREVIA)
        assertEquals(listOf("colon"), apply(filter))
    }

    @Test
    fun `la busqueda mira titulo sede barrio y tags`() {
        assertEquals(listOf("milonga"), apply(EventFilter(query = "milonga")))
        assertEquals(listOf("muestra"), apply(EventFilter(query = "recoleta")))
        assertEquals(listOf("colon"), apply(EventFilter(query = "COLÓN")))
    }

    @Test
    fun `la busqueda ignora mayusculas y espacios sobrantes`() {
        assertEquals(listOf("milonga"), apply(EventFilter(query = "  MILONGA  ")))
    }

    @Test
    fun `toggle dos veces vuelve al estado inicial`() {
        val filter = EventFilter()
            .toggleCategory(Category.MUSICA)
            .toggleCategory(Category.MUSICA)
        assertTrue(filter.isEmpty)
        assertEquals(0, filter.activeCount)
    }

    @Test
    fun `limpiar conserva la busqueda y los guardados`() {
        val filter = EventFilter(query = "tango", onlyFavorites = true)
            .toggleCategory(Category.MUSICA)
            .toggleNeighborhood("La Boca")
        val cleared = filter.cleared()

        assertEquals(0, cleared.activeCount)
        assertEquals("tango", cleared.query)
        assertTrue(cleared.onlyFavorites)
    }

    @Test
    fun `solo favoritos excluye los no guardados`() {
        val favorito = milonga.copy(isFavorite = true)
        val filter = EventFilter(onlyFavorites = true)
        assertTrue(filter.matches(favorito))
        assertFalse(filter.matches(milonga))
    }

    @Test
    fun `activeCount no cuenta la busqueda`() {
        val filter = EventFilter(query = "tango").toggleCategory(Category.CINE)
        assertEquals(1, filter.activeCount)
    }

    @Test
    fun `franja horaria se deriva de la hora de inicio`() {
        assertEquals(TimeSlot.MANANA, TimeSlot.of(LocalTime.of(11, 30)))
        assertEquals(TimeSlot.TARDE, TimeSlot.of(LocalTime.of(13, 0)))
        assertEquals(TimeSlot.NOCHE, TimeSlot.of(LocalTime.of(19, 0)))
        assertEquals(TimeSlot.SIN_HORARIO, TimeSlot.of(null))
    }

    private fun event(
        id: String,
        title: String,
        category: Category,
        neighborhood: String,
        start: LocalTime?,
        access: AccessMode,
    ) = Event(
        id = id,
        title = title,
        description = null,
        category = category,
        tags = emptyList(),
        date = LocalDate.of(2026, 8, 30),
        startTime = start,
        endTime = null,
        accessMode = access,
        reservationUrl = null,
        venue = Venue(
            id = "sede-$id",
            name = "Sede $id",
            address = "Calle 1",
            neighborhood = neighborhood,
            commune = 1,
            lat = -34.6,
            lon = -58.4,
        ),
        sourceName = null,
        sourceUrl = null,
        imageUrl = null,
    )
}

    // --- Rangos de fecha -------------------------------------------------

    @Test
    fun `el rango HOY deja solo los de hoy`() {
        val manana = milonga.copy(id = "manana", date = hoy.plusDays(1))
        val lista = listOf(milonga, manana)
        val filtro = EventFilter(dateRange = DateRangeFilter.HOY)
        assertEquals(listOf("milonga"), filtro.apply(lista, hoy).map { it.id })
    }

    @Test
    fun `el finde incluye sabado y domingo`() {
        // hoy es domingo 30-08-2026: el finde en curso es 29 y 30.
        assertTrue(DateRangeFilter.FIN_DE_SEMANA.matches(LocalDate.of(2026, 8, 29), hoy))
        assertTrue(DateRangeFilter.FIN_DE_SEMANA.matches(hoy, hoy))
        assertFalse(DateRangeFilter.FIN_DE_SEMANA.matches(LocalDate.of(2026, 8, 31), hoy))
    }

    @Test
    fun `el finde desde un dia de semana apunta al sabado siguiente`() {
        val miercoles = LocalDate.of(2026, 9, 2)
        assertTrue(DateRangeFilter.FIN_DE_SEMANA.matches(LocalDate.of(2026, 9, 5), miercoles))
        assertTrue(DateRangeFilter.FIN_DE_SEMANA.matches(LocalDate.of(2026, 9, 6), miercoles))
        assertFalse(DateRangeFilter.FIN_DE_SEMANA.matches(miercoles, miercoles))
    }

    @Test
    fun `tocar dos veces el mismo rango lo desactiva`() {
        val filtro = EventFilter()
            .toggleDateRange(DateRangeFilter.HOY)
            .toggleDateRange(DateRangeFilter.HOY)
        assertEquals(DateRangeFilter.TODAS, filtro.dateRange)
        assertEquals(0, filtro.activeCount)
    }

    // --- Ordenamiento ----------------------------------------------------

    @Test
    fun `orden por fecha ascendente y descendente son inversos`() {
        val manana = milonga.copy(id = "manana", date = hoy.plusDays(1))
        val lista = listOf(manana, milonga)
        val asc = EventFilter(sortOrder = SortOrder.FECHA_ASC).apply(lista, hoy).map { it.id }
        val desc = EventFilter(sortOrder = SortOrder.FECHA_DESC).apply(lista, hoy).map { it.id }
        assertEquals(listOf("milonga", "manana"), asc)
        assertEquals(listOf("manana", "milonga"), desc)
    }

    @Test
    fun `dentro del mismo dia ordena por hora y los sin horario van al final`() {
        val sinHora = milonga.copy(id = "sin-hora", startTime = null)
        val lista = listOf(sinHora, colon, muestra)
        val orden = EventFilter(sortOrder = SortOrder.FECHA_ASC).apply(lista, hoy).map { it.id }
        assertEquals(listOf("muestra", "colon", "sin-hora"), orden)
    }

    @Test
    fun `orden alfabetico ignora mayusculas y no agrupa por dia`() {
        val orden = EventFilter(sortOrder = SortOrder.TITULO).apply(all, hoy).map { it.id }
        assertEquals(listOf("milonga", "muestra", "colon"), orden)
        assertFalse(SortOrder.TITULO.groupsByDay)
        assertTrue(SortOrder.FECHA_ASC.groupsByDay)
    }

    @Test
    fun `el orden no cuenta como filtro activo`() {
        val filtro = EventFilter(sortOrder = SortOrder.FECHA_DESC)
        assertEquals(0, filtro.activeCount)
        assertTrue(filtro.isEmpty)
    }

    @Test
    fun `limpiar conserva el orden elegido`() {
        val filtro = EventFilter(sortOrder = SortOrder.TITULO).toggleCategory(Category.MUSICA)
        assertEquals(SortOrder.TITULO, filtro.cleared().sortOrder)
    }
