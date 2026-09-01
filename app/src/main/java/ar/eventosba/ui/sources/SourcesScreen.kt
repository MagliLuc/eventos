package ar.eventosba.ui.sources

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.outlined.OpenInNew
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ar.eventosba.domain.model.SourceStatus
import ar.eventosba.util.NativeIntents

/**
 * Panel de fuentes: de dónde sale la agenda y cómo viene cada una.
 *
 * El interruptor oculta los eventos de esa fuente **en este teléfono**. No
 * apaga el scraper, que corre en GitHub Actions y no se puede tocar desde acá;
 * el cartel del final lo dice para que no parezca que el interruptor falló.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SourcesScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: SourcesViewModel = viewModel(factory = SourcesViewModel.Factory),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("Fuentes") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Volver")
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item { Resumen(state, onEnableAll = viewModel::enableAll) }

            items(state.rows, key = { it.source.id }) { row ->
                SourceCard(
                    row = row,
                    onToggle = { viewModel.setEnabled(row.source.id, it) },
                )
            }

            if (state.loaded && state.rows.isEmpty()) {
                item {
                    Text(
                        "Todavía no bajamos el estado de las fuentes. Actualizá " +
                            "la agenda desde la pantalla principal.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            item {
                Spacer(Modifier.height(8.dp))
                Text(
                    "Apagar una fuente oculta sus eventos en este teléfono. " +
                        "No detiene la recolección, que corre en un servidor.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun Resumen(state: SourcesUiState, onEnableAll: () -> Unit) {
    if (!state.loaded) return

    if (state.allDisabled) {
        // Sin esto, apagar todo deja la agenda vacía y parece que la app se
        // rompió. El camino de vuelta tiene que estar a la vista.
        Card(
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.errorContainer,
            ),
            shape = RoundedCornerShape(12.dp),
        ) {
            Column(Modifier.padding(14.dp)) {
                Text(
                    "Apagaste todas las fuentes",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    "Por eso la agenda se ve vacía.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.height(4.dp))
                TextButton(onClick = onEnableAll, contentPadding = PaddingValues(0.dp)) {
                    Text("Volver a mostrar todas")
                }
            }
        }
        return
    }

    val atencion = state.needAttention
    Text(
        text = if (atencion == 0) {
            "${state.rows.size} fuentes, ${state.visibleEvents} eventos visibles."
        } else {
            "${state.rows.size} fuentes, ${state.visibleEvents} eventos visibles. " +
                "$atencion necesita${if (atencion == 1) "" else "n"} atención."
        },
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun SourceCard(row: SourceRow, onToggle: (Boolean) -> Unit) {
    val context = LocalContext.current
    val source = row.source

    Card(
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        text = source.name,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(Modifier.height(4.dp))
                    StatusChip(source.status)
                }
                Switch(
                    checked = row.enabled,
                    onCheckedChange = onToggle,
                    // "Activado/desactivado" a secas no dice de qué: quien usa
                    // lector de pantalla necesita saber qué prende y qué apaga.
                    modifier = Modifier.semantics {
                        contentDescription = if (row.enabled) {
                            "Ocultar los eventos de ${source.name}"
                        } else {
                            "Mostrar los eventos de ${source.name}"
                        }
                    },
                )
            }

            Spacer(Modifier.height(8.dp))
            Text(
                text = source.detail,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            if (source.url != null) {
                Spacer(Modifier.height(8.dp))
                TextButton(onClick = { NativeIntents.openUrl(context, source.url) }) {
                    Icon(Icons.Outlined.OpenInNew, contentDescription = null,
                        modifier = Modifier.size(15.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("Ver el sitio", style = MaterialTheme.typography.labelMedium)
                }
            }
        }
    }
}

@Composable
private fun StatusChip(status: SourceStatus) {
    val color = status.color()
    Surface(
        color = color.copy(alpha = 0.14f),
        contentColor = color,
        shape = RoundedCornerShape(6.dp),
    ) {
        Text(
            text = status.label,
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 7.dp, vertical = 3.dp),
        )
    }
}

/**
 * El color refuerza, nunca informa solo: al lado siempre está la etiqueta en
 * texto, porque un chip verde y uno amarillo son el mismo chip para quien no
 * distingue esos colores.
 */
@Composable
private fun SourceStatus.color(): Color = when (this) {
    SourceStatus.OK -> Color(0xFF2E7D32)
    SourceStatus.INCOMPLETA -> Color(0xFFB26A00)
    SourceStatus.SIN_EVENTOS -> MaterialTheme.colorScheme.onSurfaceVariant
    SourceStatus.ERROR -> MaterialTheme.colorScheme.error
    SourceStatus.DESCONOCIDA -> MaterialTheme.colorScheme.onSurfaceVariant
}
