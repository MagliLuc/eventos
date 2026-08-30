package ar.eventosba

import android.app.Application
import android.content.Context
import ar.eventosba.work.SyncWorker
import org.osmdroid.config.Configuration

class EventosApplication : Application() {

    override fun onCreate() {
        super.onCreate()

        // osmdroid exige un User-Agent propio: los servidores de tiles de
        // OpenStreetMap bloquean el default y, sin esto, el mapa queda gris.
        Configuration.getInstance().apply {
            // SharedPreferences propias en vez de las default: evita
            // arrastrar androidx.preference solo para esta linea.
            load(this@EventosApplication, getSharedPreferences("osmdroid", Context.MODE_PRIVATE))
            userAgentValue = BuildConfig.APPLICATION_ID
            // Cache de tiles en el almacenamiento privado de la app: no
            // requiere permisos y se borra al desinstalar.
            osmdroidBasePath = cacheDir.resolve("osmdroid")
            osmdroidTileCache = cacheDir.resolve("osmdroid/tiles")
        }

        SyncWorker.schedule(this)
    }
}
