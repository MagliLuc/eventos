package ar.eventosba.ui.map

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Directions
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ar.eventosba.domain.model.Event
import ar.eventosba.ui.home.HomeViewModel
import ar.eventosba.util.NativeIntents

/**
 * Mapa de sedes con OpenStreetMap.
 *
 * Comparte el [HomeViewModel] a proposito: los chips de filtro que el usuario
 * ya aplico en la lista siguen valiendo aca, y no hay una segunda carga.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MapScreen(
    onBack: () -> Unit,
    onEventClick: (String) -> Unit,
    modifier: Modifier = Modifier,
    viewModel: HomeViewModel = viewModel(factory = HomeViewModel.Factory),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var selected by remember { mutableStateOf<Event?>(null) }

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("Mapa de sedes") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Volver a la lista",
                        )
                    }
                },
            )
        },
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            OsmMap(
                events = state.events,
                onMarkerClick = { selected = it },
                modifier = Modifier.fillMaxSize(),
            )

            // Ficha inferior al tocar un pin. Se muestra sobre el mapa en vez
            // de navegar, para no perder el contexto geografico.
            selected?.let { event ->
                SelectedEventSheet(
                    event = event,
                    onDetails = { onEventClick(event.id) },
                    onDismiss = { selected = null },
                    modifier = Modifier.align(Alignment.BottomCenter),
                )
            }
        }
    }
}

@Composable
private fun SelectedEventSheet(
    event: Event,
    onDetails: () -> Unit,
    onDismiss: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current

    Surface(
        modifier = modifier.fillMaxWidth().padding(12.dp),
        shape = MaterialTheme.shapes.large,
        tonalElevation = 3.dp,
        shadowElevation = 6.dp,
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(
                text = event.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                text = listOfNotNull(
                    event.timeLabel,
                    event.venue.name,
                    event.venue.neighborhood,
                ).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                Button(onClick = { NativeIntents.openDirections(context, event) }) {
                    Icon(Icons.Outlined.Directions, contentDescription = null)
                    Spacer(Modifier.padding(horizontal = 3.dp))
                    Text("Cómo llegar")
                }
                OutlinedButton(onClick = { NativeIntents.addToCalendar(context, event) }) {
                    Icon(Icons.Outlined.CalendarMonth, contentDescription = null)
                    Spacer(Modifier.padding(horizontal = 3.dp))
                    Text("Agendar")
                }
            }
            Spacer(Modifier.height(4.dp))
            Row {
                androidx.compose.material3.TextButton(onClick = onDetails) { Text("Ver detalle") }
                androidx.compose.material3.TextButton(onClick = onDismiss) { Text("Cerrar") }
            }
        }
    }
}
