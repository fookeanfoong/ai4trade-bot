# Keep JavaScript interfaces (none currently, but safe if added later).
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
# AndroidX WebView support library.
-keep class androidx.webkit.** { *; }
