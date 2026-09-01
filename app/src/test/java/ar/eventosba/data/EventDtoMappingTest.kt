package ar.eventosba.data

import ar.eventosba.data.remote.EventsFeedDto
import ar.eventosba.data.remote.NetworkModule
import ar.eventosba.data.remote.toEntity
import ar.eventosba.domain.model.SourceStatus
// decodeFromString reificado es extension de StringFormat en
// kotlinx.serialization (core): sin este import no resuelve.
import kotlinx.serialization.decodeFromString
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test
import java.time.LocalDate
import java.time.LocalTime

/**
 * Contrato con el feed. Si el JSON de `docs/events.json` cambia de forma,
 * estos tests fallan antes de que la app llegue a un telefono.
 */
class EventDtoMappingTest {

    private val json = NetworkModule.json

    private val feedSample = """
        {
          "schema_version": 1,
          "generated_at": "2026-08-30T06:00:00-03:00",
          "events": [
            {
              "id": "planetario-bondi-tanguero-2026-08-30",
              "title": "Bondi Tanguero",
              "description": "Milonga al aire libre",
              "category": "MUSICA",
              "tags": ["tango", "aire-libre"],
              "date": "2026-08-30",
              "start_time": "14:00",
              "end_time": "17:00",
              "all_day": false,
              "access_mode": "INGRESO_LIBRE",
              "reservation_url": null,
              "venue": {
                "id": "planetario-galileo-galilei",
                "name": "Planetario Galileo Galilei",
                "address": "Av. Sarmiento y Belisario Roldán",
                "neighborhood": "Palermo",
                "commune": 14,
                "lat": -34.5697,
                "lon": -58.4118
              },
              "source_name": "Turismo Buenos Aires",
              "source_url": "https://turismo.buenosaires.gob.ar/es/eventos",
              "image_url": null,
              "updated_at": "2026-08-30T06:00:00-03:00"
            }
          ]
        }
    """.trimIndent()

    @Test
    fun `parsea el feed completo`() {
        val feed = json.decodeFromString<EventsFeedDto>(feedSample)
        assertEquals(1, feed.schemaVersion)
        assertEquals(1, feed.events.size)
        assertEquals("Bondi Tanguero", feed.events.first().title)
    }

    @Test
    fun `mapea a entidad de Room con horarios y coordenadas`() {
        val entity = json.decodeFromString<EventsFeedDto>(feedSample)
            .events.first().toEntity()

        assertNotNull(entity)
        requireNotNull(entity)
        assertEquals(LocalDate.of(2026, 8, 30), entity.date)
        assertEquals(LocalTime.of(14, 0), entity.startTime)
        assertEquals(LocalTime.of(17, 0), entity.endTime)
        assertEquals("Palermo", entity.venue.neighborhood)
        assertEquals(14, entity.venue.commune)
        assertEquals(listOf("tango", "aire-libre"), entity.tags)
    }

    @Test
    fun `un campo desconocido no rompe el parseo`() {
        // Permite agregar campos al feed sin dejar sin servicio a las
        // versiones de la app ya instaladas.
        val withExtra = feedSample.replace(
            """"title": "Bondi Tanguero",""",
            """"title": "Bondi Tanguero", "precio_estimado": 0,""",
        )
        val feed = json.decodeFromString<EventsFeedDto>(withExtra)
        assertEquals(1, feed.events.size)
    }

    @Test
    fun `una fecha corrupta descarta solo ese evento`() {
        val broken = feedSample.replace(""""date": "2026-08-30",""", """"date": "30/08/2026",""")
        val dto = json.decodeFromString<EventsFeedDto>(broken).events.first()
        assertNull(dto.toEntity())
    }

    @Test
    fun `una hora invalida no invalida el evento`() {
        val broken = feedSample.replace(""""start_time": "14:00",""", """"start_time": "25:99",""")
        val entity = json.decodeFromString<EventsFeedDto>(broken).events.first().toEntity()
        assertNotNull(entity)
        assertNull(entity?.startTime)
    }

    // --- bloque de fuentes -----------------------------------------------

    private val feedConFuentes = """
        {
          "schema_version": 1,
          "generated_at": "2026-09-01T06:00:00-03:00",
          "sources": [
            {
              "id": "museo-moderno",
              "name": "Museo Moderno",
              "url": "https://museomoderno.org/agenda/",
              "status": "OK",
              "detail": "40 eventos de 30 actividades leídas.",
              "events": 40,
              "items_read": 30
            },
            {
              "id": "teatro-colon",
              "name": "Teatro Colón",
              "status": "SIN_EVENTOS",
              "detail": "El sitio responde, pero ninguna es gratuita ahora.",
              "events": 0,
              "items_read": 38
            }
          ],
          "events": []
        }
    """.trimIndent()

    @Test
    fun `mapea el bloque de fuentes a entidades`() {
        val feed = json.decodeFromString<EventsFeedDto>(feedConFuentes)
        val fuentes = feed.sources.map { it.toEntity() }

        assertEquals(2, fuentes.size)
        assertEquals("museo-moderno", fuentes[0].id)
        assertEquals("OK", fuentes[0].status)
        assertEquals(40, fuentes[0].events)
        // Sin `url` en el JSON el campo queda nulo, no en cadena vacia.
        assertNull(fuentes[1].url)
        assertEquals("SIN_EVENTOS", fuentes[1].status)
    }

    @Test
    fun `un feed sin bloque de fuentes no rompe`() {
        // El JSON ya publicado no lo trae. La app tiene que seguir andando
        // contra el feed viejo mientras el scraper no se actualice.
        val feed = json.decodeFromString<EventsFeedDto>(feedSample)
        assertEquals(emptyList<Any>(), feed.sources)
    }

    @Test
    fun `un estado desconocido no crashea la app`() {
        // Si el scraper agrega un estado nuevo, una app vieja no puede
        // reventar: cae en DESCONOCIDA y lo muestra como tal.
        assertEquals(SourceStatus.DESCONOCIDA, SourceStatus.fromRaw("INVENTADO"))
        assertEquals(SourceStatus.DESCONOCIDA, SourceStatus.fromRaw(null))
        assertEquals(SourceStatus.INCOMPLETA, SourceStatus.fromRaw("incompleta"))
    }

    @Test
    fun `source_id viaja del feed a la entidad`() {
        val feed = json.decodeFromString<EventsFeedDto>(feedConSourceId)
        assertEquals("curada", feed.events.first().toEntity()!!.sourceId)
    }

    private val feedConSourceId = """
        {
          "schema_version": 1,
          "events": [
            {
              "id": "x", "title": "X", "category": "OTROS", "date": "2026-09-01",
              "access_mode": "INGRESO_LIBRE",
              "venue": { "id": "v", "name": "V" },
              "source_name": "Palacio Libertad",
              "source_id": "curada"
            }
          ]
        }
    """.trimIndent()

    // --- Ampliacion al AMBA ----------------------------------------------

    @Test
    fun `zone y contribution viajan del feed a la entidad`() {
        val entidad = json.decodeFromString<EventsFeedDto>(feedAmba)
            .events.first().toEntity()!!
        assertEquals("CONURBANO_NORTE", entidad.venue.zone)
        assertEquals("A_LA_GORRA", entidad.contribution)
        assertEquals("San Isidro", entidad.venue.neighborhood)
    }

    @Test
    fun `un feed anterior al AMBA no rompe y queda en CABA`() {
        // Es el feed que hoy esta publicado: sin `zone` ni `contribution`.
        // Un evento de entonces era de CABA, que es el valor por defecto, y
        // la contribucion ausente es lo mismo que no ser a la gorra.
        val entidad = json.decodeFromString<EventsFeedDto>(feedConSourceId)
            .events.first().toEntity()!!
        assertEquals("CABA", entidad.venue.zone)
        assertNull(entidad.contribution)
    }

    private val feedAmba = """
        {
          "schema_version": 1,
          "events": [
            {
              "id": "y", "title": "Y", "category": "TEATRO", "date": "2026-09-02",
              "access_mode": "RESERVA_PREVIA",
              "contribution": "A_LA_GORRA",
              "venue": {
                "id": "sala", "name": "Sala", "address": "Av. Mitre 500",
                "neighborhood": "San Isidro", "zone": "CONURBANO_NORTE"
              },
              "source_id": "alternativa-teatral"
            }
          ]
        }
    """.trimIndent()

}
