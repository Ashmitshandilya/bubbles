package `in`.heybubbles.app.ui.screens.fitness

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonObject
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.bool
import `in`.heybubbles.app.data.fmtNum
import `in`.heybubbles.app.data.num
import `in`.heybubbles.app.data.obj
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.theme.Bubbles

/** Fitness inside the app: a hub and its pages. Every number comes from the server; every safety rule is the server's. */
@Composable
fun FitnessScreen(api: Api, onBack: () -> Unit) {
    var page by rememberSaveable { mutableStateOf("hub") }
    when (page) {
        "setup" -> BodySetupScreen(api, onBack = { page = "hub" })
        "food" -> FoodLogScreen(api, onBack = { page = "hub" })
        "diet" -> DietScreen(api, onBack = { page = "hub" })
        "workouts" -> WorkoutsScreen(api, onBack = { page = "hub" })
        "progress" -> ProgressScreen(api, onBack = { page = "hub" })
        "transform" -> TransformScreen(api, onBack = { page = "hub" }, open = { page = it })
        else -> FitnessHub(api, onBack = onBack, open = { page = it })
    }
}

@Composable
private fun FitnessHub(api: Api, onBack: () -> Unit, open: (String) -> Unit) {
    val loader = rememberLoad(api, "/fitness/summary")
    FitnessPage("Your day, gently", onBack = onBack) {
        Text("Everything here is an estimate that moves with you. Close is good enough.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        LoadGate(loader) { s ->
            val targets = s.obj("targets")
            if (targets == null) {
                BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintPink) {
                    Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text("Let's set up your numbers", style = MaterialTheme.typography.titleMedium)
                        Text(s.str("message") ?: "Add a few details so Bubbles can work out calories, protein and water for you.", style = MaterialTheme.typography.bodyMedium)
                        Pill("Add my details", Bubbles.Pink, Bubbles.White) { open("setup") }
                    }
                }
            } else TodayCard(s, targets) { open("food") }

            Tool("Calorie calculator", "Say what you ate in your own words. Bubbles turns it into an estimate you confirm.", if ((s.num("entries") ?: 0.0) > 0) "Logged today" else "Not logged") { open("food") }
            Tool("Diet planner", "A week of meals that fit your food, allergies and numbers, with swaps and a grocery list.", if (s.bool("has_diet_plan") == true) "Plan ready" else "Not started") { open("diet") }
            Tool("Workouts", "A gentle weekly plan that adapts to your energy, sleep and any sore spots.", if (s.bool("has_workout_plan") == true) "Plan ready" else "Not started") { open("workouts") }
            Tool("Strict transformation", "A structured, safety-checked plan toward a target weight. Careful screening first.", s.obj("transform")?.str("status")?.replaceFirstChar { it.uppercase() } ?: "Not started") { open("transform") }
            Tool("Progress", "Weight trend and measurements.", "") { open("progress") }
            Tool("Your details", "Height, weight, food style, equipment and life stage.", if (targets == null) "Needed" else "") { open("setup") }
            ClinicalNote(s.obj("review"))
            Disclaimer()
        }
    }
}

@Composable
private fun Tool(title: String, text: String, status: String, onClick: () -> Unit) {
    BubbleCard(Modifier.fillMaxWidth(), onClick = onClick) {
        Row(Modifier.padding(horizontal = 18.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleMedium)
                Text(text, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            if (status.isNotEmpty()) Pill(status, MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun TodayCard(s: JsonObject, t: JsonObject, onLog: () -> Unit) {
    val budget = s.obj("budget")
    val eaten = budget?.num("eaten_kcal") ?: 0.0
    val goal = budget?.num("budget_kcal") ?: t.num("kcal") ?: 0.0
    val logged = s.bool("intake_logged") != false
    val fraction = if (goal > 0) (eaten / goal).toFloat().coerceIn(0f, 1f) else 0f
    val ringColor = Bubbles.Mint
    val track = MaterialTheme.colorScheme.surfaceVariant
    BubbleCard(Modifier.fillMaxWidth(), tint = Bubbles.TintMint) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Today (estimate)", style = MaterialTheme.typography.titleSmall)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                Box(Modifier.size(110.dp).semantics { contentDescription = if (logged) "${fmtNum(eaten)} of about ${fmtNum(goal)} kilocalories eaten today, estimate" else "Nothing logged today yet" }, contentAlignment = Alignment.Center) {
                    Canvas(Modifier.size(110.dp)) {
                        val stroke = Stroke(width = 14.dp.toPx(), cap = StrokeCap.Round)
                        val inset = 7.dp.toPx()
                        val size = Size(this.size.width - inset * 2, this.size.height - inset * 2)
                        drawArc(track, 0f, 360f, false, Offset(inset, inset), size, style = stroke)
                        if (fraction > 0f) drawArc(ringColor, -90f, 360f * fraction, false, Offset(inset, inset), size, style = stroke)
                    }
                    Text(if (logged) fmtNum(eaten) else "–", style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
                }
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("of about ${fmtNum(goal)} kcal", style = MaterialTheme.typography.bodyLarge)
                    budget?.num("remaining_kcal")?.let {
                        Text(if (!logged) "Nothing logged yet" else if (it >= 0) "About ${fmtNum(it)} kcal left" else "A little over, and that is fine", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    val water = t.num("water_ml")
                    if (water != null) Text("Water goal about ${"%.1f".format(water / 1000.0)} L", style = MaterialTheme.typography.bodyMedium)
                    t.num("steps")?.let { Text("Steps goal ${fmtNum(it)}", style = MaterialTheme.typography.bodyMedium) }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Macro("Protein", t.num("protein_g"), (s.obj("eaten")?.num("protein_g")))
                Macro("Carbs", t.num("carbs_g"), (s.obj("eaten")?.num("carbs_g")))
                Macro("Fat", t.num("fat_g"), (s.obj("eaten")?.num("fat_g")))
            }
            Pill("Log a meal", Bubbles.Pink, Bubbles.White, onClick = onLog)
        }
    }
}

@Composable
private fun Macro(name: String, target: Double?, eaten: Double?) {
    Column {
        Text(name, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("${fmtNum(eaten ?: 0.0)} / ${fmtNum(target)} g", style = MaterialTheme.typography.bodyMedium)
    }
}
