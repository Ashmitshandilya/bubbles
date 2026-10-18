package `in`.heybubbles.app.ui.theme

import androidx.compose.ui.graphics.Color

/** Brand tokens, copied from DESIGN.md so the app and the website stay one brand. */
object Bubbles {
    val Pink = Color(0xFFFF5FA2); val PinkInk = Color(0xFFD6246F); val PinkDeep = Color(0xFFA8155A)
    val Grape = Color(0xFF6A45F5); val GrapeDeep = Color(0xFF4A2BC7)
    val Sun = Color(0xFFFFC83D); val SunDeep = Color(0xFF7A5300)
    val Mint = Color(0xFF22C39A); val MintDeep = Color(0xFF0D6B52)
    val Sky = Color(0xFF1F7FD6); val SkyDeep = Color(0xFF11589A)
    val Peach = Color(0xFFFF9F6B); val PeachDeep = Color(0xFF9A3A12)
    val Urgent = Color(0xFFC42B3B)

    val TintPink = Color(0xFFFFE3EF); val TintGrape = Color(0xFFEEE8FF); val TintSun = Color(0xFFFFF1C2)
    val TintMint = Color(0xFFDDF7EE); val TintSky = Color(0xFFE0F1FF); val TintPeach = Color(0xFFFFE9DF)
    val TintUrgent = Color(0xFFFDE2E4)

    val Ink = Color(0xFF2B1A3F); val InkSoft = Color(0xFF5E4E73); val InkFaint = Color(0xFF7A6B8C)
    val Blush = Color(0xFFFFF6FA); val White = Color(0xFFFFFFFF); val SurfaceSoft = Color(0xFFFFFBFD)
    val Line = Color(0xFFF6DCE9); val LineStrong = Color(0xFFEBC3D7)

    // Dark: a deep plum ground so pink and grape still glow, never pure black.
    val NightGround = Color(0xFF1B1226); val NightSurface = Color(0xFF261A34); val NightRaised = Color(0xFF30223F)
    val NightLine = Color(0xFF3F2F52); val NightInk = Color(0xFFF7ECF6); val NightInkSoft = Color(0xFFC9B8D6)
    val NightPink = Color(0xFFFF8CC2)
}
