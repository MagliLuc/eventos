package ar.eventosba.data

import ar.eventosba.data.remote.EventsFeedDto
import ar.eventosba.data.remote.NetworkModule
import ar.eventosba.data.remote.toEntity
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
}
