package `in`.heybubbles.app.ui

import androidx.compose.material.icons.materialIcon
import androidx.compose.material.icons.materialPath
import androidx.compose.ui.graphics.vector.ImageVector

/** A round chat bubble with a small tail: the Talk tab and the empty chat. Drawn here so the app needs no extended icon set. */
val ChatBubbleIcon: ImageVector = materialIcon(name = "ChatBubble") {
    materialPath {
        moveTo(12f, 3f)
        curveTo(6.9f, 3f, 3f, 6.6f, 3f, 11f)
        curveTo(3f, 13.3f, 4.1f, 15.4f, 5.9f, 16.8f)
        lineTo(5f, 20.5f)
        lineTo(9.1f, 18.7f)
        curveTo(10f, 18.9f, 11f, 19f, 12f, 19f)
        curveTo(17.1f, 19f, 21f, 15.4f, 21f, 11f)
        curveTo(21f, 6.6f, 17.1f, 3f, 12f, 3f)
        close()
    }
}
