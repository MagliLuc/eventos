package ar.eventosba.work

import android.content.Context
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import ar.eventosba.di.AppContainer
import java.util.concurrent.TimeUnit

/**
 * Refresco diario en segundo plano.
 *
 * WorkManager respeta la bateria y la conexion del usuario, y no necesita
 * ningun servicio push (que costaria dinero o exigiria una cuenta): el JSON
 * se actualiza una vez por dia y con eso alcanza.
 */
class SyncWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val repository = AppContainer.from(applicationContext).eventRepository
        return repository.refresh().fold(
            onSuccess = { Result.success() },
            // `retry` reintenta con backoff; si el feed sigue caido manana,
            // la app igual funciona con la cache.
            onFailure = { if (runAttemptCount < 3) Result.retry() else Result.failure() },
        )
    }

    companion object {
        private const val UNIQUE_NAME = "daily-events-sync"

        fun schedule(context: Context) {
            val request = PeriodicWorkRequestBuilder<SyncWorker>(1, TimeUnit.DAYS)
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build(),
                )
                .setBackoffCriteria(
                    androidx.work.BackoffPolicy.EXPONENTIAL,
                    30,
                    TimeUnit.MINUTES,
                )
                .build()

            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                UNIQUE_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                request,
            )
        }
    }
}
