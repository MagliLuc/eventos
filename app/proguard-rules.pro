# kotlinx.serialization: conservar los serializers generados.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class ar.eventosba.data.remote.** {
    *** Companion;
}
-keepclasseswithmembers class ar.eventosba.data.remote.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Retrofit
-keepattributes Signature, RuntimeVisibleAnnotations, AnnotationDefault
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation

# osmdroid
-keep class org.osmdroid.** { *; }
-dontwarn org.osmdroid.**
