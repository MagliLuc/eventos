package ar.eventosba.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.outlined.Map
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import ar.eventosba.domain.model.Event
import ar.eventosba.ui.common.friendlyLabel
import java.time.LocalDate

/**
 * Pantalla principal: buscador, chips de filtro y lista agrupada por dia.
 *
 * Todo el filtrado ocurre sobre la lista ya cacheada en Room, asi que la
 * pantalla responde igual de rapido con o sin conexion.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onEventClick: (String) -> Unit,
    onMapClick: () -> Unit,
    modifier: Modifier = Modifier,
    viewModel: HomeViewModel = viewModel(factory = HomeViewModel.Factory),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        modifier = modifier,
        topBar = {
            TopAppBar(
                title = { Text("Eventos gratuitos") },
                actions = {
                    IconButton(onClick = viewModel::onFavoritesToggle) {
                        Icon(
                            imageVector = if (state.filter.onlyFavorites) {
                                Icons.Filled.Bookmark
                            } else {
                                Icons.Outlined.BookmarkBorder
                            },
                            contentDescription = if (state.filter.onlyFavorites) {
                                "Mostrar toda la agenda"
                            } else {
                                "Mostrar solo guardados"
                            },
                        )
                    }
                    IconButton(onClick = onMapClick) {
                        Icon(Icons.Outlined.Map, contentDescription = "Ver en el mapa")
                    }
                },
            )
        },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {

            OutlinedTextField(
                value = state.filter.query,
                onValueChange = viewModel::onQueryChange,
                placeholder = { Text("Buscar por título, sede o barrio") },
                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                singleLine = true,
                shape = MaterialTheme.shapes.medium,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 14.dp, vertical = 6.dp),
            )

            FilterBar(
                filter = state.filter,
                countByCategory = state.countByCategory,
                neighborhoods = state.availableNeighborhoods,
                dateRanges = state.availableDateRanges(),
                resultCount = state.events.size,
                onCategoryToggle = viewModel::onCategoryToggle,
                onNeighborhoodToggle = viewModel::onNeighborhoodToggle,
                onTimeSlotToggle = viewModel::onTimeSlotToggle,
                onAccessModeToggle = viewModel::onAccessModeToggle,
                onDateRangeToggle = viewModel::onDateRangeToggle,
                onSortOrderChange = viewModel::onSortOrderChange,
                onClear = viewModel::clearFilters,
            )

            state.errorMessage?.let { message ->
                OfflineBanner(message = message, onRetry = viewModel::refresh)
            }

            Spacer(Modifier.height(6.dp))

            when {
                state.isRefreshing && state.hasNoDataAtAll -> LoadingState()
                state.isEmpty -> EmptyState(
                    hasNoDataAtAll = state.hasNoDataAtAll,
                    onRetry = viewModel::refresh,
                    onClearFilters = viewModel::clearFilters,
                )
                else -> EventList(
                    events = state.events,
                    groupByDay = state.filter.sortOrder.groupsByDay,
                    onEventClick = onEventClick,
                    onFavoriteClick = viewModel::toggleFavorite,
                )
            }
        }
    }
}

@Composable
private fun EventList(
    events: List<Event>,
    groupByDay: Boolean,
    onEventClick: (String) -> Unit,
    onFavoriteClick: (String) -> Unit,
) {
    val today = LocalDate.now()

    LazyColumn(
        contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (groupByDay) {
            // Encabezado por dia: evita leer la misma fecha veinte veces.
            // Solo tiene sentido con orden cronologico; en alfabetico las
            // fechas se intercalan y los encabezados serian ruido.
            events.groupBy { it.date }.forEach { (date, dayEvents) ->
                item(key = "header-$date") {
                    DayHeader(label = date.friendlyLabel(today), count = dayEvents.size)
                }
                items(dayEvents, key = { it.id }) { event ->
                    EventCard(
                        event = event,
                        onClick = { onEventClick(event.id) },
                        onFavoriteClick = { onFavoriteClick(event.id) },
                    )
                }
            }
        } else {
            items(events, key = { it.id }) { event ->
                EventCard(
                    event = event,
                    onClick = { onEventClick(event.id) },
                    onFavoriteClick = { onFavoriteClick(event.id) },
                )
            }
        }
    }
}

@Composable
private fun DayHeader(label: String, count: Int) {
    Row(
        Modifier.fillMaxWidth().padding(top = 6.dp, bottom = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold,
        )
        Text(
            text = if (count == 1) "1 evento" else "$count eventos",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun OfflineBanner(message: String, onRetry: () -> Unit) {
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = MaterialTheme.shapes.medium,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 6.dp),
    ) {
        Row(
            Modifier.padding(start = 12.dp, end = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = message,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.weight(1f),
            )
            TextButton(onClick = onRetry) { Text("Reintentar") }
        }
    }
}

@Composable
private fun LoadingState() {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        CircularProgressIndicator()
    }
}

@Composable
private fun EmptyState(
    hasNoDataAtAll: Boolean,
    onRetry: () -> Unit,
    onClearFilters: () -> Unit,
) {
    Box(Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = if (hasNoDataAtAll) {
                    "Todavía no descargamos la agenda"
                } else {
                    "No hay eventos con estos filtros"
                },
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(6.dp))
            Text(
                text = if (hasNoDataAtAll) {
                    "Conectate una vez para bajar los eventos; después funciona sin internet."
                } else {
                    "Probá quitar alguno o cambiar la fecha."
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(10.dp))
            TextButton(onClick = if (hasNoDataAtAll) onRetry else onClearFilters) {
                Text(if (hasNoDataAtAll) "Reintentar" else "Limpiar filtros")
            }
        }
    }
}
