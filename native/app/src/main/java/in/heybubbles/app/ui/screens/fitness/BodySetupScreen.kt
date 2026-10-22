package `in`.heybubbles.app.ui.screens.fitness

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import `in`.heybubbles.app.data.Api
import `in`.heybubbles.app.data.FitnessCalc
import `in`.heybubbles.app.data.arr
import `in`.heybubbles.app.data.bool
import `in`.heybubbles.app.data.num
import `in`.heybubbles.app.data.obj
import `in`.heybubbles.app.data.str
import `in`.heybubbles.app.data.strs
import `in`.heybubbles.app.ui.components.BubbleCard
import `in`.heybubbles.app.ui.components.CheckRow
import `in`.heybubbles.app.ui.components.ChoiceChips
import `in`.heybubbles.app.ui.components.Eyebrow
import `in`.heybubbles.app.ui.components.FieldRow
import `in`.heybubbles.app.ui.components.MultiChips
import `in`.heybubbles.app.ui.components.Pill
import `in`.heybubbles.app.ui.components.TagField
import `in`.heybubbles.app.ui.theme.Bubbles
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

private val ACTIVITY = listOf(
    "sedentary" to "Mostly sitting", "light" to "Light: some walking", "moderate" to "Moderate: active most days",
    "very_active" to "Very active", "extra_active" to "Extra active: physical job and training",
)
private val DIET = listOf(
    "" to "No particular style", "vegetarian" to "Vegetarian", "vegan" to "Vegan", "eggetarian" to "Eggetarian",
    "jain" to "Jain", "non-vegetarian" to "Non-vegetarian", "halal" to "Halal",
)
private val EQUIPMENT = listOf("home" to "Mat, chair, step", "dumbbell" to "Dumbbells", "band" to "Resistance bands", "bike" to "Bike", "gym" to "Gym", "pool" to "Pool")
private val FIELD_KEYS = listOf("birth_date", "height_cm", "weight_kg", "target_weight_kg", "formula_basis", "activity_level", "diet_style")

@Composable
fun BodySetupScreen(api: Api, onBack: () -> Unit) {
    val loader = rememberLoad(api, "/profile/body")
    FitnessPage("A few details about you", "Fitness setup", onBack) {
        Text(
            "Bubbles only asks what it needs to work out your estimates. Everything marked optional can wait, and you can change any answer later.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        LoadGate(loader) { data -> SetupForm(api, data, onBack) }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun SetupForm(api: Api, data: JsonObject, onBack: () -> Unit) {
    val p = data.obj("profile") ?: JsonObject(emptyMap())
    val known = data.obj("known")
    val send = rememberSender(api)

    var imperial by remember { mutableStateOf(p.str("units") == "imperial") }
    var birth by remember { mutableStateOf(p.str("birth_date").orEmpty()) }
    val heightCmInit = p.num("height_cm")
    var heightCm by remember { mutableStateOf(heightCmInit?.let { FitnessCalc.weightText(it, false) }.orEmpty()) }
    var ft by remember { mutableStateOf(heightCmInit?.let { FitnessCalc.cmToFtIn(it).first.toString() }.orEmpty()) }
    var inch by remember { mutableStateOf(heightCmInit?.let { FitnessCalc.cmToFtIn(it).second.toString() }.orEmpty()) }
    var weight by remember { mutableStateOf(FitnessCalc.weightText(p.num("weight_kg") ?: known?.num("latest_weight_kg"), imperial)) }
    var target by remember { mutableStateOf(FitnessCalc.weightText(p.num("target_weight_kg"), imperial)) }
    var basis by remember { mutableStateOf(p.str("formula_basis").orEmpty()) }
    var activity by remember { mutableStateOf(p.str("activity_level") ?: "light") }
    var diet by remember { mutableStateOf(p.str("diet_style").orEmpty()) }
    var cuisines by remember { mutableStateOf(p.strs("cuisines")) }
    var likes by remember { mutableStateOf(p.strs("likes")) }
    var dislikes by remember { mutableStateOf(p.strs("dislikes")) }
    var equipment by remember { mutableStateOf(p.strs("equipment").toSet()) }
    var injuries by remember { mutableStateOf(p.strs("injuries")) }
    var menstruating by remember { mutableStateOf(p.bool("menstruating") == true) }
    var pregnant by remember { mutableStateOf(p.bool("pregnant") == true) }
    var breastfeeding by remember { mutableStateOf(p.bool("breastfeeding") == true) }
    var conceive by remember { mutableStateOf(p.bool("trying_to_conceive") == true) }
    var errors by remember { mutableStateOf<Map<String, String>>(emptyMap()) }
    var saved by remember { mutableStateOf(false) }
    var pickDate by remember { mutableStateOf(false) }

    fun switchUnits(next: Boolean) {
        if (next == imperial) return
        val w = FitnessCalc.weightKg(weight, imperial)
        val t = FitnessCalc.weightKg(target, imperial)
        if (next) {
            heightCm.toDoubleOrNull()?.let { val (f, i) = FitnessCalc.cmToFtIn(it); ft = f.toString(); inch = i.toString() }
        } else if (ft.isNotBlank() || inch.isNotBlank()) {
            heightCm = FitnessCalc.weightText(FitnessCalc.ftInToCm(ft.toIntOrNull() ?: 0, inch.toIntOrNull() ?: 0), false)
        }
        weight = FitnessCalc.weightText(w, next)
        target = FitnessCalc.weightText(t, next)
        imperial = next
    }

    data.arr("missing").takeIf { it.isNotEmpty() }?.let { m ->
        Text("Still needed: ${m.joinToString(", ") { it.toString().trim('"').replace('_', ' ') }}.", style = MaterialTheme.typography.bodyMedium, color = Bubbles.PinkInk)
    }
    ClinicalNote(data.obj("review"))

    BubbleCard(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("What Bubbles already knows", style = MaterialTheme.typography.titleSmall)
            Text("From your Records. If something is out of date, fix it there and Bubbles will pick it up.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Known("Conditions", known?.strs("conditions").orEmpty())
            Known("Medications", known?.strs("medications").orEmpty())
            Known("Allergies", known?.strs("allergies").orEmpty())
        }
    }

    Eyebrow("Needed for your numbers")
    ChoiceChips("Units", listOf("metric" to "Metric (kg, cm)", "imperial" to "Imperial (lb, ft)"), if (imperial) "imperial" else "metric", { switchUnits(it == "imperial") })
    Row(verticalAlignment = androidx.compose.ui.Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        FieldRow("Birth date (YYYY-MM-DD)", birth, { birth = it }, Modifier.weight(1f), error = errors["birth_date"], hint = "Used for your age only.", maxLength = 10)
        Pill("Pick", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer) { pickDate = true }
    }
    if (pickDate) {
        val state = rememberDatePickerState(selectableDates = object : androidx.compose.material3.SelectableDates {
            override fun isSelectableDate(utcTimeMillis: Long) = utcTimeMillis <= System.currentTimeMillis()
        })
        DatePickerDialog(
            onDismissRequest = { pickDate = false },
            confirmButton = { TextButton({ state.selectedDateMillis?.let { birth = Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate().toString() }; pickDate = false }) { Text("OK") } },
            dismissButton = { TextButton({ pickDate = false }) { Text("Cancel") } },
        ) { DatePicker(state) }
    }
    if (!imperial) FieldRow("Height", heightCm, { heightCm = it }, number = true, suffix = "cm", error = errors["height_cm"], hint = "Between 120 and 230")
    else Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        FieldRow("Height", ft, { ft = it }, Modifier.weight(1f), number = true, suffix = "ft", error = errors["height_cm"], maxLength = 1)
        FieldRow("and", inch, { inch = it }, Modifier.weight(1f), number = true, suffix = "in", maxLength = 2)
    }
    FieldRow("Weight now", weight, { weight = it }, number = true, suffix = if (imperial) "lb" else "kg", error = errors["weight_kg"], maxLength = 6)
    ChoiceChips(
        "Which formula should Bubbles use?", listOf("female" to "Female", "male" to "Male", "average" to "Average of both"), basis, { basis = it },
        hint = "Used only for the energy formula, which estimates how many calories a body uses. You choose, and it says nothing about who you are.",
    )
    errors["formula_basis"]?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
    ChoiceChips("How active is a usual week?", ACTIVITY, activity, { activity = it })

    Eyebrow("Optional: your goal and food")
    FieldRow("Target weight (optional)", target, { target = it }, number = true, suffix = if (imperial) "lb" else "kg", error = errors["target_weight_kg"], maxLength = 6)
    ChoiceChips("Diet style", DIET, diet, { diet = it })
    errors["diet_style"]?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
    TagField("Cuisines you enjoy", cuisines, { cuisines = it }, listOf("North Indian", "South Indian", "Gujarati", "Bengali", "Continental"))
    TagField("Foods you like", likes, { likes = it }, listOf("rajma", "paneer", "dal", "poha", "curd"))
    TagField("Foods you would rather not have", dislikes, { dislikes = it }, listOf("bitter gourd", "mushroom", "brinjal"))

    Eyebrow("Optional: movement")
    MultiChips("What can you use?", EQUIPMENT, equipment, { equipment = it }, hint = "No equipment is fine. Pick nothing and Bubbles keeps to body-weight moves.")
    TagField("Injuries or sore spots", injuries, { injuries = it }, listOf("knee", "lower back", "shoulder", "ankle"), hint = "Bubbles steers around these.")

    Eyebrow("Optional: life stage")
    Text("These change which plans are suitable. Bubbles keeps strict plans for adults who are none of these.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    CheckRow("I have periods", menstruating) { menstruating = it }
    CheckRow("I am pregnant", pregnant) { pregnant = it }
    CheckRow("I am breastfeeding", breastfeeding) { breastfeeding = it }
    CheckRow("I am trying to conceive", conceive) { conceive = it }

    send.error.value?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium) }
    if (saved) Text("Saved. Bubbles will use these details for your fitness numbers.", style = MaterialTheme.typography.bodyMedium, color = Bubbles.MintDeep)
    Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Pill(if (send.busy.value) "Saving…" else "Save my details", Bubbles.Pink, Bubbles.White) {
            val errs = mutableMapOf<String, String>()
            val cm = if (imperial) FitnessCalc.ftInToCm(ft.toIntOrNull() ?: 0, inch.toIntOrNull() ?: 0) else heightCm.replace(',', '.').toDoubleOrNull() ?: 0.0
            val w = FitnessCalc.weightKg(weight, imperial)
            val t = FitnessCalc.weightKg(target, imperial)
            if (birth.isBlank()) errs["birth_date"] = "Add your birth date. Bubbles uses it for your age."
            else if (runCatching { LocalDate.parse(birth) }.isFailure) errs["birth_date"] = "Use the form 1995-04-23, or tap Pick."
            if (cm <= 0) errs["height_cm"] = "Add your height."
            if (w == null) errs["weight_kg"] = "Add your weight."
            if (basis.isBlank()) errs["formula_basis"] = "Choose one. You can pick Average if you prefer."
            errors = errs; saved = false
            if (errs.isNotEmpty()) return@Pill
            val body = buildJsonObject {
                put("units", if (imperial) "imperial" else "metric"); put("birth_date", birth); put("height_cm", cm); put("weight_kg", w!!)
                if (t != null) put("target_weight_kg", t) else put("target_weight_kg", "")
                put("formula_basis", basis); put("activity_level", activity); put("diet_style", diet)
                put("cuisines", JsonArray(cuisines.map(::JsonPrimitive))); put("likes", JsonArray(likes.map(::JsonPrimitive)))
                put("dislikes", JsonArray(dislikes.map(::JsonPrimitive))); put("equipment", JsonArray(equipment.map(::JsonPrimitive)))
                put("injuries", JsonArray(injuries.map(::JsonPrimitive)))
                put("menstruating", menstruating); put("pregnant", pregnant); put("breastfeeding", breastfeeding); put("trying_to_conceive", conceive)
            }
            send.send("PUT", "/profile/body", body) { saved = true }
        }
        if (saved) Pill("Back to Fitness", MaterialTheme.colorScheme.surfaceVariant, MaterialTheme.colorScheme.onSurface, onClick = onBack)
    }
    // The server names the field first ("height_cm must be between 120 and 230"): show it under that field.
    val serverMsg = send.error.value
    if (serverMsg != null) FIELD_KEYS.firstOrNull { serverMsg.lowercase().startsWith(it) }?.let { key -> if (errors[key] != serverMsg) errors = errors + (key to serverMsg) }
}

@Composable
private fun Known(title: String, items: List<String>) {
    Column(Modifier.padding(top = 6.dp)) {
        Text(title, style = MaterialTheme.typography.labelLarge)
        Text(if (items.isEmpty()) "Nothing recorded" else items.joinToString(", "), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
