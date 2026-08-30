plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
}

android {
    namespace = "ar.eventosba"
    compileSdk = 35

    defaultConfig {
        applicationId = "ar.eventosba"
        minSdk = 24
        targetSdk = 35
        versionCode = 1
        versionName = "1.0.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // URL del feed servido gratis por GitHub Pages. Cambiala por la tuya
        // (Settings -> Pages) o apuntala a un raw.githubusercontent.com.
        buildConfigField(
            "String",
            "EVENTS_FEED_URL",
            "\"https://magliluc.github.io/eventos/events.json\"",
        )
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            // Firmamos el release con la clave de debug para que `assembleRelease`
            // funcione sin secretos en CI. Para publicar en una tienda,
            // reemplazar por un signingConfig propio.
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        // osmdroid y algunas libs usan APIs de java.time en minSdk 24.
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

ksp {
    // Exporta el schema de Room: permite versionar migraciones en git.
    arg("room.schemaLocation", "$projectDir/schemas")
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    // collectAsStateWithLifecycle: recoleccion consciente del ciclo de vida.
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons)
    implementation(libs.androidx.navigation.compose)
    debugImplementation(libs.androidx.compose.ui.tooling)

    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    implementation(libs.retrofit)
    implementation(libs.retrofit.serialization)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    // Referenciado desde NetworkModule (source set main), por eso no es debugOnly;
    // el interceptor solo se instala cuando BuildConfig.DEBUG es true.
    implementation(libs.okhttp.logging)

    implementation(libs.androidx.work.runtime)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.coil.compose)

    // OpenStreetMap: sin API key, sin tarjeta de credito, licencia Apache 2.0.
    implementation(libs.osmdroid.android)

    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.1.3")

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.room.testing)
}
