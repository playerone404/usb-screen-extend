# Building the Android APK

This guide covers three methods for building the USB Second Screen Android app.

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| **JDK** | 17 | OpenJDK 17 recommended. [Download](https://adoptium.net/) |
| **Android SDK** | API 34 | compileSdk and targetSdk |
| **Android Build Tools** | 34.x | Included with SDK |
| **Gradle** | 8.7 | Wrapper included in the project |
| **Kotlin** | 1.9.24 | Managed by Gradle plugin |

## Method 1: Android Studio (Easiest)

This is the simplest way to build and is recommended for most users.

### Step 1: Install Android Studio

Download and install [Android Studio](https://developer.android.com/studio) (Ladybug 2024.2 or later recommended).

During installation, make sure the following are selected:
- Android SDK
- Android SDK Platform API 34
- Android SDK Build-Tools

### Step 2: Open the Project

1. Open Android Studio
2. Select **File → Open** (or **Open** from the welcome screen)
3. Navigate to the `android/` directory in this project and select it
4. Click **OK**

### Step 3: Wait for Gradle Sync

Android Studio will automatically:
- Download the Gradle wrapper (if missing)
- Download all dependencies
- Index the project

This may take a few minutes the first time. Watch the bottom status bar for progress.

> [!TIP]
> If Gradle sync fails with a JDK error, go to **File → Settings → Build, Execution, Deployment → Build Tools → Gradle** and set **Gradle JDK** to JDK 17.

### Step 4: Build the APK

**For a debug APK:**
- Click **Build → Build Bundle(s) / APK(s) → Build APK(s)**
- The APK will be at: `android/app/build/outputs/apk/debug/app-debug.apk`

**To run directly on a connected phone:**
- Connect your phone via USB with USB Debugging enabled
- Click the green **Run ▶** button (or Shift+F10)
- Select your device and click OK

## Method 2: Command Line with Gradle Wrapper

### Step 1: Install JDK 17

**Fedora:**
```bash
sudo dnf install java-17-openjdk-devel
```

**Ubuntu / Debian:**
```bash
sudo apt install openjdk-17-jdk
```

**Arch Linux:**
```bash
sudo pacman -S jdk17-openjdk
```

Verify:
```bash
java -version   # Should show version 17.x
javac -version  # Should show version 17.x
```

### Step 2: Install Android SDK

If you don't have Android Studio, install the command-line tools:

```bash
# Set up ANDROID_HOME
export ANDROID_HOME="$HOME/Android/Sdk"
mkdir -p "$ANDROID_HOME"
```

Download the [Android command-line tools](https://developer.android.com/studio#command-line-tools-only) and extract them:

```bash
# Download (check for latest URL at the link above)
cd /tmp
wget https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip commandlinetools-linux-*.zip

# Install to the correct path
mkdir -p "$ANDROID_HOME/cmdline-tools"
mv cmdline-tools "$ANDROID_HOME/cmdline-tools/latest"
```

Add to your shell profile (`~/.bashrc` or `~/.zshrc`):
```bash
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
```

Reload:
```bash
source ~/.bashrc   # or source ~/.zshrc
```

### Step 3: Install SDK Packages

```bash
sdkmanager --update
sdkmanager "platforms;android-34" "build-tools;34.0.0" "platform-tools"
```

Accept the licenses:
```bash
sdkmanager --licenses
```

### Step 4: Set Up the Gradle Wrapper

The project includes `gradle/wrapper/gradle-wrapper.properties` but may be missing the wrapper scripts. Generate them:

```bash
cd android/

# If you have Gradle installed globally:
gradle wrapper

# This creates gradlew, gradlew.bat, and gradle/wrapper/gradle-wrapper.jar
```

> [!NOTE]
> If you don't have Gradle installed globally, Android Studio generates these files for you, or you can download them from a fresh Gradle project.

### Step 5: Create `local.properties`

Create `android/local.properties` with your SDK path:
```bash
echo "sdk.dir=$ANDROID_HOME" > local.properties
```

### Step 6: Build

```bash
# Debug build
./gradlew assembleDebug

# The APK is at:
# app/build/outputs/apk/debug/app-debug.apk
```

```bash
# Release build (unsigned)
./gradlew assembleRelease

# The APK is at:
# app/build/outputs/apk/release/app-release-unsigned.apk
```

## Method 3: Command Line Tools Only (No Android Studio)

This method uses only `sdkmanager` and command-line tools — no Android Studio needed.

### Step 1: Install JDK 17

See [Method 2, Step 1](#step-1-install-jdk-17) above.

### Step 2: Download Command Line Tools

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
mkdir -p "$ANDROID_HOME"

# Download the latest command-line tools
cd /tmp
wget https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip
unzip commandlinetools-linux-*.zip
mkdir -p "$ANDROID_HOME/cmdline-tools"
mv cmdline-tools "$ANDROID_HOME/cmdline-tools/latest"

# Add to PATH
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
```

### Step 3: Install Required SDK Packages

```bash
sdkmanager "platforms;android-34" "build-tools;34.0.0" "platform-tools"
sdkmanager --licenses   # Accept all licenses
```

### Step 4: Clone and Set Up the Project

```bash
git clone https://github.com/user/usb-second-screen.git
cd usb-second-screen/android

# Create local.properties
echo "sdk.dir=$ANDROID_HOME" > local.properties
```

### Step 5: Generate the Gradle Wrapper

If `gradlew` is not present:

```bash
# Option A: Install Gradle and generate wrapper
# Fedora:  sudo dnf install gradle
# Ubuntu:  sudo apt install gradle
# Arch:    sudo pacman -S gradle
gradle wrapper

# Option B: Download wrapper scripts manually from gradle.org
# and place gradle-wrapper.jar in gradle/wrapper/
```

### Step 6: Build the APK

```bash
./gradlew assembleDebug
```

The APK will be at `app/build/outputs/apk/debug/app-debug.apk`.

## Signing the APK for Release

Debug APKs are automatically signed with a debug keystore. For distribution, you need a release signing key.

### Step 1: Generate a Keystore

```bash
keytool -genkey -v \
    -keystore usb-second-screen-release.jks \
    -keyalg RSA -keysize 2048 \
    -validity 10000 \
    -alias release
```

You'll be prompted for a password and identity information.

> [!CAUTION]
> Keep your keystore file and password safe. If you lose them, you cannot update your app on devices that have the old version installed.

### Step 2: Configure Signing in Gradle

Create or edit `android/keystore.properties` (do **not** commit this file):

```properties
storeFile=../usb-second-screen-release.jks
storePassword=your_keystore_password
keyAlias=release
keyPassword=your_key_password
```

If the project's `build.gradle.kts` has a signing config placeholder, it will read from this file. Otherwise, you can sign manually (see Step 3).

### Step 3: Sign Manually with `apksigner`

```bash
# Build the unsigned release APK
./gradlew assembleRelease

# Align the APK
zipalign -v 4 \
    app/build/outputs/apk/release/app-release-unsigned.apk \
    app-release-aligned.apk

# Sign it
apksigner sign \
    --ks usb-second-screen-release.jks \
    --ks-key-alias release \
    --out app-release-signed.apk \
    app-release-aligned.apk

# Verify the signature
apksigner verify --verbose app-release-signed.apk
```

> [!NOTE]
> `zipalign` and `apksigner` are in `$ANDROID_HOME/build-tools/34.0.0/`.

## Installing the APK via adb

### Prerequisites

- Phone connected via USB
- USB Debugging enabled in Developer Options
- Phone authorized (tap "Allow" on the phone when prompted)

### Install

```bash
# Verify the phone is connected
adb devices

# Install debug APK
adb install -r android/app/build/outputs/apk/debug/app-debug.apk

# Install signed release APK
adb install -r app-release-signed.apk
```

### Useful adb Commands

```bash
# List connected devices
adb devices

# Install APK (replace existing)
adb install -r path/to/app.apk

# Uninstall the app
adb uninstall com.example.secondscreen

# Launch the app
adb shell am start -n com.example.secondscreen/.MainActivity

# View app logs
adb logcat -s UsbSecondScreen

# Set up the reverse tunnel manually
adb reverse tcp:7878 tcp:7878

# Check active reverse tunnels
adb reverse --list
```
