plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.did.charactersheet"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.did.charactersheet"
        minSdk = 24
        targetSdk = 35
        versionCode = 14
        versionName = "0.8.0"
    }

    buildTypes {
        debug {
            // Keep the Phase 9 Test 2 package stable so each feedback build
            // updates the existing test app instead of creating another icon.
            applicationIdSuffix = ".phase9test2"
            versionNameSuffix = "-phase9-test2-v7"
        }

        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )

            val storeFilePath = System.getenv("DID_RELEASE_STORE_FILE")
            if (!storeFilePath.isNullOrBlank()) {
                signingConfig = signingConfigs.create("didRelease") {
                    storeFile = file(storeFilePath)
                    storePassword = System.getenv("DID_RELEASE_STORE_PASSWORD")
                    keyAlias = System.getenv("DID_RELEASE_KEY_ALIAS")
                    keyPassword = System.getenv("DID_RELEASE_KEY_PASSWORD")
                }
            }
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
        buildConfig = true
    }

    sourceSets {
        getByName("main").java.srcDir("../phase8")
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-compose:1.10.1")
    implementation("androidx.lifecycle:lifecycle-viewmodel-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")

    implementation(platform("androidx.compose:compose-bom:2024.12.01"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    debugImplementation("androidx.compose.ui:ui-tooling")

    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.journeyapps:zxing-android-embedded:4.3.0")
    implementation("com.caverock:androidsvg-aar:1.4")
}
