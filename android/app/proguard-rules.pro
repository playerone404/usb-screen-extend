# ProGuard / R8 rules for USB Second Screen
# ============================================

# Keep the main application classes
-keep class com.example.secondscreen.** { *; }

# Keep the Activity (referenced by manifest)
-keep public class * extends android.app.Activity

# Keep SurfaceHolder.Callback implementations
-keep class * implements android.view.SurfaceHolder$Callback {
    public *;
}

# Keep classes that use MediaCodec callbacks
-keep class * extends android.media.MediaCodec$Callback {
    public *;
}

# General Android rules

# Keep Parcelable implementations
-keep class * implements android.os.Parcelable {
    public static final android.os.Parcelable$Creator *;
}

# Keep Serializable classes
-keepclassmembers class * implements java.io.Serializable {
    static final long serialVersionUID;
    private static final java.io.ObjectStreamField[] serialPersistentFields;
    private void writeObject(java.io.ObjectOutputStream);
    private void readObject(java.io.ObjectInputStream);
    java.lang.Object writeReplace();
    java.lang.Object readResolve();
}

# Don't warn about missing annotations
-dontwarn javax.annotation.**
-dontwarn kotlin.Unit

# Keep Kotlin metadata for reflection (if needed in future)
-keep class kotlin.Metadata { *; }

# Remove logging in release builds
-assumenosideeffects class android.util.Log {
    public static int v(...);
    public static int d(...);
    public static int i(...);
}

# Optimization settings
-optimizationpasses 5
-dontusemixedcaseclassnames
-verbose
