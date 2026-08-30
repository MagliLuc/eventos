package ar.eventosba.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bookmark
import androidx.compose.material.icons.outlined.BookmarkBorder
import androidx.compose.material.icons.outlined.CalendarMonth
import androidx.compose.material.icons.outlined.Place
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import ar.eventosba.domain.model.AccessMode
import ar.eventosba.domain.model.Category
import ar.eventosba.domain.model.Event
import ar.eventosba.domain.model.Venue
import ar.eventosba.ui.theme.EventosTheme
import ar.eventosba.ui.theme.accent
import ar.eventosba.util.NativeIntents
import java.time.LocalDate
import java.time.LocalTime

/**
 * Tarjeta de evento del feed.
 *
 * Muestra de un vistazo lo que decide si vale la pena ir: horario, sede,
 * barrio y sobre todo la modalidad de ingreso (si hay que reservar antes,
 * enterarse al llegar es tarde).
 */
@Composable
fun EventCard(
    event: Event,
    onClick: () -> Unit,
    onFavoriteClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current

    Card(
        onClick = onClick,
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        elevation = CardDefaults.cardElevation(defaultElevation = 1.dp),
    ) {
        // IntrinsicSize.Min hace que la barra de categoria tome exactamente
        // el alto del contenido de la tarjeta.
        Row(Modifier.height(IntrinsicSize.Min)) {
            // Marca de categoria: refuerzo visual, nunca la unica pista.
            Box(
                Modifier
                    .width(5.dp)
                    .fillMaxHeight()
                    .background(event.category.accent()),
            )

            Column(Modifier.padding(14.dp).weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CategoryTag(event.category)
                    Spacer(Modifier.width(6.dp))
                    AccessTag(event.accessMode)
                }

                Spacer(Modifier.height(8.dp))
                Text(
                    text = event.title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )

                Spacer(Modifier.height(6.dp))
                event.timeLabel?.let { InfoRow(Icons.Outlined.Schedule, it) }
                InfoRow(
                    icon = Icons.Outlined.Place,
                    text = listOfNotNull(event.venue.name, event.venue.neighborhood)
                        .joinToString(" · "),
                )

                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    QuickAction(
                        icon = Icons.Outlined.CalendarMonth,
                        label = "Agendar",
                        onClick = { NativeIntents.addToCalendar(context, event) },
                    )
                    if (event.venue.hasCoordinates) {
                        QuickAction(
                            icon = Icons.Outlined.Place,
                            label = "Cómo llegar",
                            onClick = { NativeIntents.openDirections(context, event) },
                        )
                    }
                }
            }

            IconButton(onClick = onFavoriteClick, modifier = Modifier.padding(4.dp)) {
                Icon(
                    imageVector = if (event.isFavorite) {
                        Icons.Filled.Bookmark
                    } else {
                        Icons.Outlined.BookmarkBorder
                    },
                    contentDescription = if (event.isFavorite) {
                        "Quitar ${event.title} de guardados"
                    } else {
                        "Guardar ${event.title}"
                    },
                    tint = if (event.isFavorite) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                )
            }
        }
    }
}

@Composable
private fun CategoryTag(category: Category) {
    Surface(
        color = category.accent().copy(alpha = 0.14f),
        contentColor = category.accent(),
        shape = RoundedCornerShape(6.dp),
    ) {
        Text(
            text = category.label.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.Bold,
            modifier = Modifier.padding(horizontal = 7.dp, vertical = 3.dp),
        )
    }
}

@Composable
private fun AccessTag(mode: AccessMode) {
    // La reserva previa es la unica que exige actuar antes: se destaca.
    val highlighted = mode == AccessMode.RESERVA_PREVIA
    Surface(
        color = if (highlighted) {
            MaterialTheme.colorScheme.primary.copy(alpha = 0.14f)
        } else {
            Color.Transparent
        },
        contentColor = if (highlighted) {
            MaterialTheme.colorScheme.primary
        } else {
            MaterialTheme.colorScheme.onSurfaceVariant
        },
        shape = RoundedCornerShape(6.dp),
    ) {
        Text(
            text = mode.shortLabel,
            style = MaterialTheme.typography.labelSmall,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 3.dp),
        )
    }
}

@Composable
private fun InfoRow(icon: androidx.compose.ui.graphics.vector.ImageVector, text: String) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(top = 2.dp),
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null, // el texto de al lado ya lo dice
            modifier = Modifier.size(14.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.width(6.dp))
        Text(
            text = text,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun QuickAction(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    label: String,
    onClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.semantics { contentDescription = label },
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
        ) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(15.dp))
            Spacer(Modifier.width(5.dp))
            Text(label, style = MaterialTheme.typography.labelMedium)
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun EventCardPreview() {
    EventosTheme(dynamicColor = false) {
        Box(Modifier.padding(12.dp)) {
            EventCard(
                event = Event(
                    id = "preview",
                    title = "Gran Milonga de Cierre del Festival de Tango",
                    description = null,
                    category = Category.MUSICA,
                    tags = listOf("tango"),
                    date = LocalDate.now(),
                    startTime = LocalTime.of(17, 0),
                    endTime = LocalTime.of(20, 30),
                    accessMode = AccessMode.ORDEN_DE_LLEGADA,
                    reservationUrl = null,
                    venue = Venue(
                        "usina-del-arte", "Usina del Arte", "Caffarena 1",
                        "La Boca", 4, -34.639, -58.3576,
                    ),
                    sourceName = "Tango BA",
                    sourceUrl = null,
                    imageUrl = null,
                    isFavorite = true,
                ),
                onClick = {},
                onFavoriteClick = {},
            )
        }
    }
}
