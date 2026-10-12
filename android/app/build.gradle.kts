plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.taalbrug.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.taalbrug.app"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        compose = true
    }
    // the desktop database is bundled as the starting data (copied on first launch only)
    sourceSets["main"].assets.srcDir(layout.buildDirectory.dir("generated/seedAssets"))
}

// snapshot of the desktop app's database (../files/vocabulary.db), taken at build time
val copySeedDatabase by tasks.registering(Copy::class) {
    from(rootProject.file("../files/vocabulary.db"))
    into(layout.buildDirectory.dir("generated/seedAssets"))
}
tasks.named("preBuild") { dependsOn(copySeedDatabase) }

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.09.03"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.compose.ui:ui-tooling-preview")
    debugImplementation("androidx.compose.ui:ui-tooling")
    implementation("androidx.activity:activity-compose:1.9.2")
    implementation("androidx.core:core-ktx:1.13.1")
}
