package ar.eventosba.ui.home

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ExpandLess
import androidx.compose.material.icons.filled.ExpandMore
import androidx.compose.material.icons.filled.Sort
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ar.eventosba.domain.model.AccessMode
import ar.eventosba.domain.model.Category
import ar.eventosba.domain.model.DateRangeFilter
import ar.eventosba.domain.model.EventFilter
import ar.eventosba.domain.model.SortOrder
import ar.eventosba.domain.model.TimeSlot

/**
 * Filtros y orden de la home.
 *
 * Se muestran siempre las dos filas que la gente usa en el 90% de los casos
 * (cuándo y de qué), y el resto —barrio, franja, modalidad— vive detrás de
 * "Más filtros". Antes eran cinco filas fijas de chips que se comían media
 * pantalla antes del primer evento.
 *
 * Dentro de una fila los valores suman en OR; entre filas se combinan en AND.
 * Es lo que la gente espera al ir tocando chips.
 */
@Composable
fun FilterBar(
    filter: EventFilter,
    countByCategory: Map<Category, Int>,
    neighborhoods: List<String>,
    dateRanges: List<DateRangeFilter>,
    resultCount: Int,
    onCategoryToggle: (Category) -> Unit,
    onNeighborhoodToggle: (String) -> Unit,
    onTimeSlotToggle: (TimeSlot) -> Unit,
    onAccessModeToggle: (AccessMode) -> Unit,
    onDateRangeToggle: (DateRangeFilter) -> Unit,
    onSortOrderChange: (SortOrder) -> Unit,
    onClear: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    // Filtros ocultos activos: si expandís, cerrás y quedaba algo puesto, no
    // se puede quedar sin ninguna pista de por qué faltan eventos.
    val hiddenActive = filter.neighborhoods.size + filter.timeSlots.size + filter.accessModes.size

    Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {

        if (dateRanges.size > 1) {
            ChipRow {
                items(dateRanges, key = { it.name }) { range ->
                    Chip(
                        label = range.label,
                        selected = filter.dateRange == range,
                        onClick = { onDateRangeToggle(range) },
                    )
                }
            }
        }

        ChipRow {
            items(
                Category.entries.filter { (countByCategory[it] ?: 0) > 0 },
                key = { it.name },
            ) { category ->
                Chip(
                    label = "${category.label} (${countByCategory[category] ?: 0})",
                    selected = category in filter.categories,
                    onClick = { onCategoryToggle(category) },
                )
            }
        }

        AnimatedVisibility(visible = expanded) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                ChipRow {
                    items(TimeSlot.entries.filter { it != TimeSlot.SIN_HORARIO }) { slot ->
                        Chip(
                            label = slot.label,
                            selected = slot in filter.timeSlots,
                            onClick = { onTimeSlotToggle(slot) },
                        )
                    }
                    items(AccessMode.entries) { mode ->
                        Chip(
                            label = mode.shortLabel,
                            selected = mode in filter.accessModes,
                            onClick = { onAccessModeToggle(mode) },
                        )
                    }
                }
                if (neighborhoods.isNotEmpty()) {
                    ChipRow {
                        items(neighborhoods, key = { it }) { neighborhood ->
                            Chip(
                                label = neighborhood,
                                selected = neighborhood in filter.neighborhoods,
                                onClick = { onNeighborhoodToggle(neighborhood) },
                            )
                        }
                    }
                }
            }
        }

        Row(
            Modifier.fillMaxWidth().padding(horizontal = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            TextButton(onClick = { expanded = !expanded }) {
                Icon(
                    imageVector = if (expanded) Icons.Filled.ExpandLess else Icons.Filled.ExpandMore,
                    contentDescription = null,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(4.dp))
                Text(
                    text = when {
                        expanded -> "Menos filtros"
                        hiddenActive > 0 -> "Más filtros ($hiddenActive)"
                        else -> "Más filtros"
                    },
                    style = MaterialTheme.typography.labelLarge,
                )
            }

            if (filter.activeCount > 0) {
                TextButton(onClick = onClear) {
                    Icon(Icons.Filled.Close, contentDescription = null, Modifier.size(15.dp))
                    Spacer(Modifier.width(3.dp))
                    Text("Limpiar", style = MaterialTheme.typography.labelLarge)
                }
            }

            Spacer(Modifier.weight(1f))

            Text(
                text = if (resultCount == 1) "1 evento" else "$resultCount eventos",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.width(4.dp))
            SortMenu(current = filter.sortOrder, onSelect = onSortOrderChange)
        }
    }
}

/** Selector de orden. Menú y no chips: son opciones excluyentes. */
@Composable
private fun SortMenu(current: SortOrder, onSelect: (SortOrder) -> Unit) {
    var open by remember { mutableStateOf(false) }

    TextButton(onClick = { open = true }) {
        Icon(Icons.Filled.Sort, contentDescription = "Ordenar", Modifier.size(18.dp))
        Spacer(Modifier.width(4.dp))
        Text(current.label, style = MaterialTheme.typography.labelLarge)
    }

    DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
        SortOrder.entries.forEach { order ->
            DropdownMenuItem(
                text = { Text(order.label) },
                onClick = {
                    onSelect(order)
                    open = false
                },
                trailingIcon = {
                    if (order == current) {
                        Icon(
                            Icons.Filled.Check,
                            contentDescription = "Orden seleccionado",
                            modifier = Modifier.size(18.dp),
                        )
                    }
                },
            )
        }
    }
}

@Composable
private fun ChipRow(content: LazyListScope.() -> Unit) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(7.dp),
        contentPadding = PaddingValues(horizontal = 14.dp),
        content = content,
    )
}

@Composable
private fun Chip(label: String, selected: Boolean, onClick: () -> Unit) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text(label, style = MaterialTheme.typography.labelLarge) },
        shape = MaterialTheme.shapes.small,
        colors = FilterChipDefaults.filterChipColors(
            selectedContainerColor = MaterialTheme.colorScheme.primary,
            selectedLabelColor = MaterialTheme.colorScheme.onPrimary,
        ),
        modifier = Modifier.height(34.dp),
    )
}
