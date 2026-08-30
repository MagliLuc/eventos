package ar.eventosba.domain

import ar.eventosba.domain.model.AccessMode
import ar.eventosba.domain.model.Category
import org.junit.Assert.assertEquals
import org.junit.Test

class CategoryMappingTest {

    @Test
    fun `mapea las categorias del feed`() {
        assertEquals(Category.MUSICA, Category.fromRaw("MUSICA"))
        assertEquals(Category.ARTES_VISUALES, Category.fromRaw("artes_visuales"))
    }

    @Test
    fun `una categoria nueva del feed cae en OTROS en vez de crashear`() {
        assertEquals(Category.OTROS, Category.fromRaw("PERFORMANCE_INMERSIVA"))
        assertEquals(Category.OTROS, Category.fromRaw(null))
    }

    @Test
    fun `una modalidad desconocida se asume ingreso libre`() {
        assertEquals(AccessMode.RESERVA_PREVIA, AccessMode.fromRaw("RESERVA_PREVIA"))
        assertEquals(AccessMode.INGRESO_LIBRE, AccessMode.fromRaw("MODALIDAD_RARA"))
    }
}
