package `in`.heybubbles.app.data

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull

/** Forgiving readers for server documents: a missing or differently-typed field is "no value", never a crash. */
fun JsonObject.str(key: String): String? = (this[key] as? JsonPrimitive)?.takeIf { it !is JsonNull }?.contentOrNull
fun JsonObject.num(key: String): Double? = (this[key] as? JsonPrimitive)?.doubleOrNull
fun JsonObject.int(key: String): Int? = (this[key] as? JsonPrimitive)?.let { it.intOrNull ?: it.doubleOrNull?.toInt() }
fun JsonObject.bool(key: String): Boolean? = (this[key] as? JsonPrimitive)?.booleanOrNull
fun JsonObject.obj(key: String): JsonObject? = this[key] as? JsonObject
fun JsonObject.arr(key: String): List<JsonElement> = (this[key] as? JsonArray) ?: emptyList()
fun JsonObject.objs(key: String): List<JsonObject> = arr(key).mapNotNull { it as? JsonObject }
fun JsonObject.strs(key: String): List<String> = arr(key).mapNotNull { (it as? JsonPrimitive)?.contentOrNull }

/** Whole numbers print without ".0"; a missing number prints as a dash so a gap never reads as zero. */
fun fmtNum(v: Double?): String = if (v == null) "–" else if (v % 1.0 == 0.0) v.toLong().toString() else "%.1f".format(v)
