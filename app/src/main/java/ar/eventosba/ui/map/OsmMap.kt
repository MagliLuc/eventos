package ar.eventosba.ui.map

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import ar.eventosba.domain.model.Event
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.BoundingBox
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Overlay
import org.osmdroid.views.overlay.OverlayItem
import org.osmdroid.views.overlay.ItemizedIconOverlay

/**
 * Encuadre inicial: el AMBA, no solo Capital.
 *
 * Solo se usa mientras no hay eventos ubicados que encuadrar -- apenas
 * llegan, `zoomToBoundingBox` los enmarca y esto deja de importar. Aun asi
 * abrir centrado en el Obelisco dejaba medio Conurbano fuera de pantalla en
 * el primer cuadro, que es la primera impresion de una agenda que ahora
 * cubre los tres cordones.
 */
private val AMBA_CENTER = GeoPoint(-34.6400, -58.5000)
private const val DEFAULT_ZOOM = 10.5

/**
 * `MapView` de osmdroid embebido en Compose.
 *
 * osmdroid es Apache 2.0 y consume tiles de OpenStreetMap: no hay API key,
 * ni cuenta de facturacion, ni cuota que se agote. A cambio hay que respetar
 * su politica de uso, por eso el User-Agent se configura en
 * `EventosApplication` y la atribucion se dibuja siempre sobre el mapa.
 */
@Composable
fun OsmMap(
    events: List<Event>,
    onMarkerClick: (Event) -> Unit,
    modifier: Modifier = Modifier,
    markerColor: Color = Color(0xFF0A5C9E),
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    // Una sola instancia de MapView para toda la vida del composable: recrearla
    // en cada recomposicion tiraria la cache de tiles y volveria a descargarlos.
    val mapView = remember {
        MapView(context).apply {
            setTileSource(TileSourceFactory.MAPNIK)
            setMultiTouchControls(true)
            // El repetido horizontal confunde en una ciudad; lo desactivamos.
            isHorizontalMapRepetitionEnabled = false
            isVerticalMapRepetitionEnabled = false
            setUseDataConnection(true)
            controller.setZoom(DEFAULT_ZOOM)
            controller.setCenter(AMBA_CENTER)
            overlays.add(AttributionOverlay())
        }
    }

    // osmdroid necesita onResume/onPause para arrancar y frenar el hilo de
    // descarga de tiles; sin esto sigue bajando datos con la app en segundo plano.
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> mapView.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView.onPause()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            mapView.onDetach()
        }
    }

    AndroidView(
        factory = { mapView },
        modifier = modifier,
        update = { view ->
            view.overlays.removeAll { it is ItemizedIconOverlay<*> }

            val located = events.filter { it.venue.hasCoordinates }
            if (located.isEmpty()) return@AndroidView

            val items = located.map { event ->
                OverlayItem(
                    event.title,
                    listOfNotNull(event.timeLabel, event.venue.name).joinToString(" · "),
                    GeoPoint(event.venue.lat!!, event.venue.lon!!),
                )
            }

            view.overlays.add(
                ItemizedIconOverlay(
                    items,
                    context.pinDrawable(markerColor.toArgb()),
                    object : ItemizedIconOverlay.OnItemGestureListener<OverlayItem> {
                        override fun onItemSingleTapUp(index: Int, item: OverlayItem): Boolean {
                            onMarkerClick(located[index])
                            return true
                        }

                        override fun onItemLongPress(index: Int, item: OverlayItem) = false
                    },
                    context,
                ),
            )

            // Encuadre automatico sobre los eventos visibles: si el usuario
            // filtro por un barrio, el mapa lo sigue.
            view.post {
                view.zoomToBoundingBox(located.boundingBox(), true, 96)
            }
            view.invalidate()
        },
    )
}

/** Caja que contiene todos los eventos, con un margen para que no queden al borde. */
private fun List<Event>.boundingBox(): BoundingBox {
    val lats = mapNotNull { it.venue.lat }
    val lons = mapNotNull { it.venue.lon }
    val padding = 0.01
    return BoundingBox(
        lats.max() + padding,
        lons.max() + padding,
        lats.min() - padding,
        lons.min() - padding,
    )
}

/**
 * La atribucion a OpenStreetMap no es decorativa: la licencia ODbL la exige
 * en cualquier mapa que use sus datos.
 */
private class AttributionOverlay : Overlay() {
    private val background = Paint().apply { color = 0xB0FFFFFF.toInt() }
    private val text = Paint().apply {
        color = 0xFF333333.toInt()
        textSize = 26f
        isAntiAlias = true
        typeface = Typeface.DEFAULT
    }

    override fun draw(canvas: Canvas, mapView: MapView?, shadow: Boolean) {
        if (shadow || mapView == null) return
        val label = "© OpenStreetMap"
        val width = text.measureText(label)
        val x = mapView.width - width - 16f
        val y = mapView.height - 14f
        canvas.drawRect(x - 8f, y - 30f, mapView.width.toFloat(), mapView.height.toFloat(), background)
        canvas.drawText(label, x, y, text)
    }
}

/** Pin dibujado en codigo: evita sumar assets y se tiñe con el color del tema. */
private fun Context.pinDrawable(color: Int): android.graphics.drawable.Drawable {
    val size = (resources.displayMetrics.density * 18).toInt().coerceAtLeast(24)
    val bitmap = android.graphics.Bitmap.createBitmap(size, size, android.graphics.Bitmap.Config.ARGB_8888)
    val canvas = Canvas(bitmap)
    val radius = size / 2f
    canvas.drawCircle(radius, radius, radius, Paint().apply {
        this.color = 0xFFFFFFFF.toInt()
        isAntiAlias = true
    })
    canvas.drawCircle(radius, radius, radius - size * 0.14f, Paint().apply {
        this.color = color
        isAntiAlias = true
    })
    return android.graphics.drawable.BitmapDrawable(resources, bitmap)
}
