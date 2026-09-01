package ar.eventosba.ui.nav

import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import ar.eventosba.ui.detail.EventDetailScreen
import ar.eventosba.ui.detail.EventDetailViewModel
import ar.eventosba.ui.home.HomeScreen
import ar.eventosba.ui.home.HomeViewModel
import ar.eventosba.ui.map.MapScreen
import ar.eventosba.ui.sources.SourcesScreen

object Routes {
    const val GRAPH = "agenda"
    const val HOME = "home"
    const val MAP = "map"
    const val SOURCES = "sources"
    const val DETAIL = "event/{${EventDetailViewModel.ARG_EVENT_ID}}"

    fun detail(eventId: String) = "event/$eventId"
}

@Composable
fun EventosNavHost(
    modifier: Modifier = Modifier,
    navController: NavHostController = rememberNavController(),
) {
    NavHost(
        navController = navController,
        startDestination = Routes.HOME,
        route = Routes.GRAPH,
        modifier = modifier,
    ) {
        composable(Routes.HOME) { entry ->
            HomeScreen(
                onEventClick = { navController.navigate(Routes.detail(it)) },
                onMapClick = { navController.navigate(Routes.MAP) },
                onSourcesClick = { navController.navigate(Routes.SOURCES) },
                viewModel = entry.sharedHomeViewModel(navController),
            )
        }

        composable(Routes.MAP) { entry ->
            MapScreen(
                onBack = navController::popBackStack,
                onEventClick = { navController.navigate(Routes.detail(it)) },
                // Mismo ViewModel que la lista: los filtros que el usuario ya
                // aplico siguen valiendo en el mapa.
                viewModel = entry.sharedHomeViewModel(navController),
            )
        }

        composable(Routes.SOURCES) {
            // ViewModel propio: el panel lee las fuentes y las preferencias,
            // no los filtros de la home.
            SourcesScreen(onBack = navController::popBackStack)
        }

        composable(
            route = Routes.DETAIL,
            arguments = listOf(
                navArgument(EventDetailViewModel.ARG_EVENT_ID) { type = NavType.StringType },
            ),
        ) {
            // El id llega por SavedStateHandle al ViewModel, asi que la
            // pantalla no necesita recibirlo por parametro.
            EventDetailScreen(onBack = navController::popBackStack)
        }
    }
}

/**
 * ViewModel compartido a nivel del grafo.
 *
 * Por defecto cada destino tiene su propio `ViewModelStore`, asi que pasar a
 * la pantalla del mapa crearia un HomeViewModel nuevo y perderia los filtros.
 * Scopeandolo al back stack entry del grafo, lista y mapa comparten estado y
 * la agenda se consulta una sola vez.
 */
@Composable
private fun NavBackStackEntry.sharedHomeViewModel(
    navController: NavHostController,
): HomeViewModel {
    val graphEntry = remember(this) { navController.getBackStackEntry(Routes.GRAPH) }
    return viewModel(viewModelStoreOwner = graphEntry, factory = HomeViewModel.Factory)
}
