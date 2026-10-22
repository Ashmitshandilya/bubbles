# Tink (used by androidx.security:security-crypto) references build-time annotations that are not shipped.
-dontwarn com.google.errorprone.annotations.**
-dontwarn javax.annotation.**
-dontwarn org.checkerframework.**
# kotlinx.serialization and OkHttp ship their own consumer rules.
