package ar.eventosba.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ar.eventosba.domain.model.AccessMode
import ar.eventosba.domain.model.Category
import ar.eventosba.domain.model.EventFilter
import ar.eventosba.domain.model.TimeSlot
import ar.eventosba.ui.common.shortLabel
import java.time.LocalDate

/**
 * Filas de chips de filtrado.
 *
 * Cada fila es una faceta independiente (categoria, barrio, franja, ingreso) y
 * dentro de una fila los valores suman en OR, mientras que entre filas se
 * combinan en AND: es la combinacion que la gente espera al tocar chips.
 */
@Composable
fun FilterBar(
    filter: EventFilter,
    countByCategory: Map<Category, Int>,
    neighborhoods: List<String>,
    dates: List<LocalDate>,
    onCategoryToggle: (Category) -> Unit,
    onNeighborhoodToggle: (String) -> Unit,
    onTimeSlotToggle: (TimeSlot) -> Unit,
    onAccessModeToggle: (AccessMode) -> Unit,
    onDateSelect: (LocalDate?) -> Unit,
    onClear: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {

        if (dates.size > 1) {
            ChipRow {
                item {
                    Chip(
                        label = "Todas las fechas",
                        selected = filter.date == null,
                        onClick = { onDateSelect(null) },
                    )
                }
                items(dates, key = { it.toString() }) { date ->
                    Chip(
                        label = date.shortLabel(),
                        selected = filter.date == date,
                        onClick = { onDateSelect(if (filter.date == date) null else date) },
                    )
                }
            }
        }

        ChipRow {
            items(Category.entries.filter { countByCategory[it].orEmpty() > 0 }) { category ->
                Chip(
                    label = "${category.label} (${countByCategory[category].orEmpty()})",
                    selected = category in filter.categories,
                    onClick = { onCategoryToggle(category) },
                )
            }
        }

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

        if (filter.activeCount > 0) {
            ChipRow {
                item {
                    Chip(
                        label = "Limpiar (${filter.activeCount})",
                        selected = false,
                        onClick = onClear,
                        leadingIcon = {
                            Icon(
                                Icons.Filled.Close,
                                contentDescription = null,
                                Modifier.size(16.dp),
                            )
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun ChipRow(content: androidx.compose.foundation.lazy.LazyListScope.() -> Unit) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(7.dp),
        contentPadding = PaddingValues(horizontal = 14.dp),
        content = content,
    )
}

@Composable
private fun Chip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    leadingIcon: @Composable (() -> Unit)? = null,
) {
    FilterChip(
        selected = selected,
        onClick = onClick,
        label = { Text(label, style = MaterialTheme.typography.labelLarge) },
        leadingIcon = leadingIcon,
        shape = MaterialTheme.shapes.small,
        colors = FilterChipDefaults.filterChipColors(
            selectedContainerColor = MaterialTheme.colorScheme.primary,
            selectedLabelColor = MaterialTheme.colorScheme.onPrimary,
        ),
        modifier = Modifier.height(34.dp),
    )
}

private fun Int?.orEmpty(): Int = this ?: 0
