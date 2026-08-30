package ar.eventosba.data.remote

import retrofit2.http.GET
import retrofit2.http.Url

/**
 * Un unico GET a un archivo estatico. No hay backend que mantener ni cuota
 * que pagar: GitHub Pages sirve el JSON con CDN y HTTPS incluidos.
 */
interface EventsApi {
    @GET
    suspend fun getEvents(@Url url: String): EventsFeedDto
}
