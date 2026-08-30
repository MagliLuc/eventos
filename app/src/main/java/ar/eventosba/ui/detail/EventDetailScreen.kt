package ar.eventosba.ui.detail

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Directions
import androidx.compose.material.icons.outlined.OpenInNew
import androidx.compose.material.icons.outlined.Share
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ar.eventosba.domain.model.AccessMode
import ar.eventosba.domain.model.Event
import ar.eventosba.ui.common.friendlyLabel
import ar.eventosba.ui.theme.accent
import ar.eventosba.util.NativeIntents

/**
 * Ficha del evento. Todas las acciones salen por Intents nativos: calendario,
 * mapas, navegador y compartir. Cero SDKs de terceros, cero costo.
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
fun EventDetailScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: EventDetailViewModel = viewModel(factory = EventDetailViewModel.Factory),
) {
    val event by viewModel.event.collectAsStateWithLifecycle()
    val context = LocalContext.current

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text(event?.category?.label ?: "Evento") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = "Volver",
                        )
                    }
                },
                actions = {
                    event?.let { current ->
                        IconButton(onClick = viewModel::toggleFavorite) {
                            Icon(
                                imageVector = if (current.isFavorite) {
                                    Icons.Filled.Bookmark
                                } else {
                                    Icons.Outlined.BookmarkBorder
                                },
                                contentDescription = if (current.isFavorite) {
                                    "Quitar de guardados"
                                } else {
                                    "Guardar evento"
                                },
                            )
                        }
                        IconButton(onClick = { NativeIntents.share(context, current) }) {
                            Icon(Icons.Outlined.Share, contentDescription = "Compartir")
                        }
                    }
                },
            )
        },
    ) { padding ->
        val current = event
        if (current == null) {
            Box(Modifier.padding(padding).fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        Column(
            Modifier
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 18.dp, vertical = 12.dp),
        ) {
            Surface(
                color = current.category.accent().copy(alpha = 0.14f),
                contentColor = current.category.accent(),
                shape = MaterialTheme.shapes.small,
            ) {
                Text(
                    text = current.category.label.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                )
            }

            Spacer(Modifier.height(10.dp))
            Text(
                text = current.title,
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.Bold,
            )

            Spacer(Modifier.height(14.dp))
            DetailRow("Cuándo", buildString {
                append(current.date.friendlyLabel())
                current.timeLabel?.let { append(" · $it") }
            })
            DetailRow("Dónde", "${current.venue.name}\n${current.venue.fullAddress}")
            DetailRow("Ingreso", current.accessMode.label)
            current.sourceName?.let { DetailRow("Fuente", it) }

            current.description?.let { description ->
                Spacer(Modifier.height(14.dp))
                HorizontalDivider()
                Spacer(Modifier.height(14.dp))
                Text(description, style = MaterialTheme.typography.bodyMedium)
            }

            if (current.accessMode == AccessMode.RESERVA_PREVIA) {
                Spacer(Modifier.height(14.dp))
                Surface(
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.10f),
                    shape = MaterialTheme.shapes.medium,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(
                        text = "Esta actividad requiere reserva digital previa. " +
                            "Conviene gestionarla con anticipación: el cupo suele agotarse.",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(12.dp),
                    )
                }
            }

            Spacer(Modifier.height(18.dp))
            ActionButtons(current)
            Spacer(Modifier.height(24.dp))
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ActionButtons(event: Event) {
    val context = LocalContext.current

    FlowRow(
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(8.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Button(onClick = { NativeIntents.addToCalendar(context, event) }) {
            Icon(Icons.Outlined.CalendarMonth, contentDescription = null)
            Spacer(Modifier.padding(horizontal = 3.dp))
            Text("Agendar")
        }

        if (event.venue.hasCoordinates || event.venue.address != null) {
            OutlinedButton(onClick = { NativeIntents.openDirections(context, event) }) {
                Icon(Icons.Outlined.Directions, contentDescription = null)
                Spacer(Modifier.padding(horizontal = 3.dp))
                Text("Cómo llegar")
            }
        }

        event.reservationUrl?.let { url ->
            OutlinedButton(onClick = { NativeIntents.openUrl(context, url) }) {
                Icon(Icons.Outlined.OpenInNew, contentDescription = null)
                Spacer(Modifier.padding(horizontal = 3.dp))
                Text("Reservar")
            }
        }

        event.sourceUrl?.let { url ->
            TextButton(onClick = { NativeIntents.openUrl(context, url) }) {
                Text("Ver publicación oficial")
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String) {
    Column(Modifier.padding(vertical = 5.dp)) {
        Text(
            text = label.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = value, style = MaterialTheme.typography.bodyLarge)
    }
}
