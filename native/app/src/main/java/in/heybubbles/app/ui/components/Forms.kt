package `in`.heybubbles.app.ui.components

import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Checkbox
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp

/** Small form pieces shared by the Fitness screens. Every target is at least 48dp and every field says what it is. */
@Composable
fun FieldRow(
    label: String, value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier,
    number: Boolean = false, hint: String? = null, error: String? = null, suffix: String? = null, maxLength: Int = 60,
) {
    OutlinedTextField(
        value, { onChange(it.take(maxLength)) }, modifier.fillMaxWidth(), label = { Text(label) }, singleLine = true, shape = MaterialTheme.shapes.medium,
        isError = error != null, suffix = suffix?.let { { Text(it) } },
        keyboardOptions = KeyboardOptions(keyboardType = if (number) KeyboardType.Decimal else KeyboardType.Text),
        supportingText = (error ?: hint)?.let { { Text(it) } },
    )
}

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
fun ChoiceChips(legend: String, options: List<Pair<String, String>>, selected: String, onSelect: (String) -> Unit, hint: String? = null) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if (legend.isNotEmpty()) Text(legend, style = MaterialTheme.typography.titleSmall)
        hint?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            options.forEach { (value, label) ->
                FilterChip(selected == value, { onSelect(value) }, label = { Text(label) }, modifier = Modifier.heightIn(min = 48.dp))
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
fun MultiChips(legend: String, options: List<Pair<String, String>>, selected: Set<String>, onChange: (Set<String>) -> Unit, hint: String? = null) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(legend, style = MaterialTheme.typography.titleSmall)
        hint?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            options.forEach { (value, label) ->
                val on = value in selected
                FilterChip(on, { onChange(if (on) selected - value else selected + value) }, label = { Text(label) }, modifier = Modifier.heightIn(min = 48.dp))
            }
        }
    }
}

@Composable
fun CheckRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().heightIn(min = 48.dp).clickable(role = Role.Checkbox) { onChange(!checked) }
            .semantics { stateDescription = if (checked) "Checked" else "Not checked" },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Checkbox(checked, null)
        Text(label, Modifier.padding(start = 8.dp), style = MaterialTheme.typography.bodyLarge)
    }
}

/** Free words as removable chips ("rajma", "knee"), with a few suggestions to tap. */
@OptIn(ExperimentalLayoutApi::class, ExperimentalMaterial3Api::class)
@Composable
fun TagField(label: String, values: List<String>, onChange: (List<String>) -> Unit, suggestions: List<String> = emptyList(), hint: String? = null) {
    var draft by remember { mutableStateOf("") }
    fun add(word: String) {
        val w = word.trim().lowercase().take(40)
        if (w.isNotEmpty() && w !in values && values.size < 20) onChange(values + w)
        draft = ""
    }
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(label, style = MaterialTheme.typography.titleSmall)
        hint?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        if (values.isNotEmpty()) FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            values.forEach { v -> FilterChip(true, { onChange(values - v) }, label = { Text("$v  ✕") }, modifier = Modifier.heightIn(min = 48.dp)) }
        }
        OutlinedTextField(
            draft, { if (it.endsWith(",")) add(it.dropLast(1)) else draft = it.take(40) }, Modifier.fillMaxWidth(), singleLine = true,
            label = { Text("Add one") }, shape = MaterialTheme.shapes.medium,
            trailingIcon = { if (draft.isNotBlank()) Pill("Add", MaterialTheme.colorScheme.primaryContainer, MaterialTheme.colorScheme.onPrimaryContainer) { add(draft) } },
        )
        val left = suggestions.filter { it.lowercase() !in values }
        if (left.isNotEmpty()) FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            left.forEach { s -> FilterChip(false, { add(s) }, label = { Text(s) }, modifier = Modifier.heightIn(min = 48.dp)) }
        }
    }
}
