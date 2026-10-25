import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

// Release signing lives OUTSIDE the repository (never commit keystores or passwords). Same file and same key as the wrapper
// app, so this app updates it in place: storeFile, storePassword, keyAlias, keyPassword.
val signingProps = Properties().apply {
    val f = file(System.getenv("BUBBLES_SIGNING_PROPERTIES") ?: "${System.getProperty("user.home")}/.bubbles-signing/keystore.properties")
    if (f.exists()) f.inputStream().use { load(it) }
}

android {
    namespace = "in.heybubbles.app"
    compileSdk = 36

    defaultConfig {
        applicationId = "in.heybubbles.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 12
        versionName = "3.2.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        // Public values only (same as the website). Override with -PBUBBLES_API_URL=... for a local server.
        buildConfigField("String", "API_URL", "\"${providers.gradleProperty("BUBBLES_API_URL").getOrElse("https://bubbles-dk3v.onrender.com")}\"")
        buildConfigField("String", "SUPABASE_URL", "\"${providers.gradleProperty("BUBBLES_SUPABASE_URL").getOrElse("")}\"")
        buildConfigField("String", "SUPABASE_KEY", "\"${providers.gradleProperty("BUBBLES_SUPABASE_KEY").getOrElse("")}\"")
    }

    signingConfigs {
        create("release") {
            if (signingProps.getProperty("storeFile") != null) {
                storeFile = file(signingProps.getProperty("storeFile"))
                storePassword = signingProps.getProperty("storePassword")
                keyAlias = signingProps.getProperty("keyAlias")
                keyPassword = signingProps.getProperty("keyPassword")
            }
        }
    }
    buildTypes {
        debug { applicationIdSuffix = ".debug"; versionNameSuffix = "-debug"; buildConfigField("boolean", "DEMO", "true") }
        // The release code (minified by R8) with demo sign-in and the debug key, to test what users will really run.
        create("qa") {
            initWith(getByName("release"))
            applicationIdSuffix = ".qa"; versionNameSuffix = "-qa"
            buildConfigField("boolean", "DEMO", "true")
            signingConfig = signingConfigs.getByName("debug")
            matchingFallbacks += "release"
        }
        release {
            isMinifyEnabled = true; isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            buildConfigField("boolean", "DEMO", "false")
            if (signingProps.getProperty("storeFile") != null) signingConfig = signingConfigs.getByName("release")
        }
    }
    buildFeatures { compose = true; buildConfig = true }
    compileOptions { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    val bom = platform("androidx.compose:compose-bom:2025.08.00")
    implementation(bom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-core")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.navigation:navigation-compose:2.9.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.9.2")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.9.2")
    implementation("androidx.core:core-splashscreen:1.0.1")
    implementation("androidx.security:security-crypto:1.1.0-alpha06")
    implementation("androidx.webkit:webkit:1.12.1")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation(platform("com.google.firebase:firebase-bom:33.7.0"))
    implementation("com.google.firebase:firebase-messaging")
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.10.2")
    debugImplementation("androidx.compose.ui:ui-tooling")
    testImplementation("junit:junit:4.13.2")
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
    // Screen tests that run on a phone or the emulator: ./gradlew connectedDebugAndroidTest
    androidTestImplementation(bom)
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
    androidTestImplementation("androidx.test:runner:1.6.2")
    androidTestImplementation("androidx.test.ext:junit:1.2.1")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}

// Firebase (phone reminders) is built in only when this machine has the project's google-services.json (it stays out of git, like the
// signing key). Without it the app builds and runs with phone reminders switched off, so CI and a fresh clone still work.
if (file("google-services.json").exists()) apply(plugin = "com.google.gms.google-services")
