package `in`.heybubbles.app.ui.screens.fitness

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import `in`.heybubbles.app.data.Api

// Temporary: each of these is replaced by a real screen in its own commit.
@Composable fun FoodLogScreen(api: Api, onBack: () -> Unit) { FitnessPage("Calorie calculator", onBack = onBack) { Text("Coming next") } }
@Composable fun DietScreen(api: Api, onBack: () -> Unit) { FitnessPage("Diet planner", onBack = onBack) { Text("Coming next") } }
@Composable fun WorkoutsScreen(api: Api, onBack: () -> Unit) { FitnessPage("Workouts", onBack = onBack) { Text("Coming next") } }
@Composable fun ProgressScreen(api: Api, onBack: () -> Unit) { FitnessPage("Progress", onBack = onBack) { Text("Coming next") } }
@Composable fun TransformScreen(api: Api, onBack: () -> Unit) { FitnessPage("Strict transformation", onBack = onBack) { Text("Coming next") } }
