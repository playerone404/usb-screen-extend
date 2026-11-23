plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.secondscreen"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.example.secondscreen"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "0.1"
    }

    signingConfigs {
        // Release signing config — fill in with your keystore details to build
        // a signed release APK. You can also set these via environment variables
        // or a local signing.properties file.
        create("release") {
            // Uncomment and fill in to enable release signing:
            // storeFile = file("path/to/your/keystore.jks")
            // storePassword = "your-store-password"
            // keyAlias = "your-key-alias"
            // keyPassword = "your-key-password"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
            // signingConfig = signingConfigs.getByName("release")  // uncomment when keystore is configured
        }
        debug {
            isMinifyEnabled = false
        }
    }

    buildFeatures {
        viewBinding = true
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
}
