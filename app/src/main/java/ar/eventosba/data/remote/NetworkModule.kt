package ar.eventosba.data.remote

import android.content.Context
import ar.eventosba.BuildConfig
import kotlinx.serialization.json.Json
import okhttp3.Cache
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * Construccion del cliente HTTP. Todo open source: OkHttp, Retrofit y
 * kotlinx.serialization.
 */
object NetworkModule {

    private const val CACHE_BYTES = 5L * 1024 * 1024

    val json: Json = Json {
        // El feed puede sumar campos nuevos sin que una version vieja de la
        // app deje de funcionar.
        ignoreUnknownKeys = true
        coerceInputValues = true
        explicitNulls = false
    }

    fun okHttpClient(context: Context): OkHttpClient = OkHttpClient.Builder()
        // La cache HTTP evita volver a bajar el JSON si no cambio (ETag).
        .cache(Cache(File(context.cacheDir, "http"), CACHE_BYTES))
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .apply {
            if (BuildConfig.DEBUG) {
                addInterceptor(
                    okhttp3.logging.HttpLoggingInterceptor().apply {
                        level = okhttp3.logging.HttpLoggingInterceptor.Level.BASIC
                    },
                )
            }
        }
        .build()

    fun eventsApi(context: Context): EventsApi = Retrofit.Builder()
        // `baseUrl` es formal: cada llamada usa @Url con la URL completa del feed.
        .baseUrl("https://example.invalid/")
        .client(okHttpClient(context))
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(EventsApi::class.java)
}
