package ar.eventosba.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import ar.eventosba.domain.model.Category

private val Azul = Color(0xFF0A5C9E)
private val AzulClaro = Color(0xFF9CCBFA)
private val Arena = Color(0xFFFAF8F5)
private val Carbon = Color(0xFF16181C)

private val LightColors = lightColorScheme(
    primary = Azul,
    onPrimary = Color.White,
    secondary = Color(0xFF4A6572),
    background = Arena,
    surface = Color.White,
    surfaceVariant = Color(0xFFEDE9E3),
)

private val DarkColors = darkColorScheme(
    primary = AzulClaro,
    onPrimary = Color(0xFF00325A),
    secondary = Color(0xFFB2CBD6),
    background = Carbon,
    surface = Color(0xFF1E2126),
    surfaceVariant = Color(0xFF2C2F36),
)

@Composable
fun EventosTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    // Material You en Android 12+; en versiones previas usamos la paleta propia.
    dynamicColor: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColors
        else -> LightColors
    }
    MaterialTheme(colorScheme = colorScheme, content = content)
}

/**
 * Color de acento por categoria.
 *
 * Se usa solo como marca lateral de la tarjeta, nunca como unico portador de
 * informacion: el nombre de la categoria siempre esta escrito al lado, asi la
 * pantalla sigue siendo legible sin distinguir colores.
 */
fun Category.accent(): Color = when (this) {
    Category.MUSICA -> Color(0xFF7B4FA8)
    Category.ARTES_VISUALES -> Color(0xFFC2571A)
    Category.CINE -> Color(0xFF1F6F6B)
    Category.TEATRO -> Color(0xFFB03A5B)
    Category.INFANTILES -> Color(0xFF2E7D32)
    Category.FERIAS -> Color(0xFFB8860B)
    Category.OTROS -> Color(0xFF5A6472)
}
