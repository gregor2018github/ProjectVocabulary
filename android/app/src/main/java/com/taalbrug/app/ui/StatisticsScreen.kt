package com.taalbrug.app.ui

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.taalbrug.app.ActivityData
import com.taalbrug.app.Logic
import com.taalbrug.app.Store
import com.taalbrug.app.Word
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.abs
import kotlin.math.roundToInt

private val RANGE_DAYS = listOf(7, 30, 90, 365)
private val LABEL_FORMAT = DateTimeFormatter.ofPattern("d MMM", Locale.ENGLISH)
private val PERIOD_FORMAT = DateTimeFormatter.ofPattern("EEE d MMM yyyy", Locale.ENGLISH)
private val SINCE_FORMAT = DateTimeFormatter.ofPattern("d MMM yyyy", Locale.ENGLISH)

/** Statistics: activity dashboard, score dashboard and the per-word list. */
@Composable
fun StatisticsScreen(onBack: () -> Unit) {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    var range by rememberSaveable { mutableIntStateOf(1) }
    Column(Modifier.fillMaxSize()) {
        ScreenHeader("Statistics", "How you train and how well you know each word", onBack)
        Segmented(listOf("Activity", "Scores", "Words"), tab, { tab = it }, Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp))
        when (tab) {
            0, 1 -> {
                val days = RANGE_DAYS[range]
                val data = remember(days, Store.revision) { ActivityData.create(days) }
                Column(
                    Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 16.dp).padding(bottom = 16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Segmented(listOf("7 days", "30 days", "90 days", "1 year"), range, { range = it }, Modifier.fillMaxWidth())
                    if (tab == 0) ActivityView(data, days) else ScoresView(data)
                }
            }
            else -> WordsView()
        }
    }
}

private fun labels(data: ActivityData) = data.buckets.map { it.format(LABEL_FORMAT) }
private fun periods(data: ActivityData) = data.buckets.map { (if (data.weekly) "Week of " else "") + it.format(PERIOD_FORMAT) }

/** Tiles two per row; an odd last tile takes the full width. */
@Composable
private fun TileGrid(tiles: List<Triple<String, String, String>>) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        tiles.chunked(2).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { (label, value, note) -> StatTile(label, value, note, Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun ColumnScope.ActivityView(data: ActivityData, days: Int) {
    val p = LocalPalette.current
    val trainedTotal = data.trained.sum()
    val unit = if (data.weekly) "week" else "day"
    TileGrid(listOf(
        Triple("Words trained", "$trainedTotal", if (trainedTotal > 0) "avg score ${data.totalPoints / trainedTotal}" else "no answers yet"),
        Triple("Days active", "${data.activeDays}", "of the last $days days"),
        Triple("Time practised", Logic.formatDuration(data.practiceSeconds), "estimated from answer times"),
        Triple("Current streak", Logic.plural(data.streak, "day"), "days in a row with training"),
        Triple("Vocabulary changes", "+${data.added.sum()}  −${data.removed.sum()}", "${Logic.plural(Store.words.size, "word")} in total"),
    ))

    val labels = labels(data)
    val periods = periods(data)
    val trainedDetails = periods.indices.map { i ->
        "${periods[i]}\n${Logic.plural(data.trained[i], "word")} trained" +
            (data.averagePoints[i]?.let { " · avg score ${it.roundToInt()}" } ?: "")
    }
    ChartPanel("Words trained", "Answers per $unit · tap a column for details", trainedDetails) { selected, onSelect ->
        BarChart(labels, data.trained, p.chartBlue, selected, onSelect, emptyText = "No training in this period")
    }

    val vocabDetails = periods.indices.map { "${periods[it]}\n+${data.added[it]} added · −${data.removed[it]} removed" }
    ChartPanel(
        "Vocabulary changes", "Words added and removed per $unit", vocabDetails,
        legend = listOf("Added" to p.chartBlue, "Removed" to p.chartRed),
    ) { selected, onSelect ->
        BarChart(labels, data.added, p.chartBlue, selected, onSelect, data.removed, p.chartRed,
            emptyText = "No words added or removed", height = 150)
    }

    val hourDetails = data.hours.mapIndexed { h, n -> "%02d:00–%02d:00\n%s trained".format(h, (h + 1) % 24, Logic.plural(n, "word")) }
    ChartPanel("Time of day", "Answers per hour of the day", hourDetails) { selected, onSelect ->
        BarChart((0 until 24).map { it.toString() }, data.hours, p.chartBlue, selected, onSelect, emptyText = "No training in this period", height = 150)
    }

    data.trackingSince?.let { Hint("Activity is recorded since ${it.format(SINCE_FORMAT)}; training before that date is not included.") }
}

@Composable
private fun ColumnScope.ScoresView(data: ActivityData) {
    val p = LocalPalette.current
    val directions = listOf(Triple("DG", "Dutch → German", p.chartBlue), Triple("GD", "German → Dutch", p.chartRed))
    val legend = directions.map { (_, name, color) -> name to color }

    val tiles = directions.map { (key, name, _) ->
        val (total, count) = data.directionTotals.getValue(key)
        Triple("Avg $name", if (count > 0) "${(total.toDouble() / count).roundToInt()}" else "—", "from ${Logic.plural(count, "answer")}")
    }.toMutableList()
    val (dgTotal, dgCount) = data.directionTotals.getValue("DG")
    val (gdTotal, gdCount) = data.directionTotals.getValue("GD")
    tiles += if (dgCount > 0 && gdCount > 0) {
        val gap = dgTotal.toDouble() / dgCount - gdTotal.toDouble() / gdCount
        val stronger = if (gap > 0) "Dutch → German" else "German → Dutch"
        Triple("Difference", "${abs(gap).roundToInt()} points", if (gap.roundToInt() != 0) "$stronger is stronger" else "both directions equal")
    } else {
        Triple("Difference", "—", "needs answers in both directions")
    }
    TileGrid(tiles)

    val labels = labels(data)
    val periods = periods(data)
    fun details(values: Map<String, List<Double?>>, withCounts: Boolean) = periods.indices.map { i ->
        (listOf(periods[i]) + directions.map { (key, name, _) ->
            val value = values.getValue(key)[i]
            if (value == null) "$name: —"
            else "$name: ${value.roundToInt()}" + if (withCounts) " (${Logic.plural(data.directionCounts.getValue(key)[i], "answer")})" else ""
        }).joinToString("\n")
    }

    val unit = if (data.weekly) "week" else "day"
    ChartPanel("Average score", "Mean rating per $unit and direction · tap for details", details(data.directionAverages, true), legend) { selected, onSelect ->
        LineChart(labels, directions.map { (key, _, color) -> data.directionAverages.getValue(key) to color }, selected, onSelect)
    }
    ChartPanel("Running average", "Mean of all answers from the start of the period up to each point", details(data.directionRunning, false), legend) { selected, onSelect ->
        LineChart(labels, directions.map { (key, _, color) -> data.directionRunning.getValue(key) to color }, selected, onSelect, height = 170)
    }

    data.trackingSince?.let { Hint("Scores are recorded since ${it.format(SINCE_FORMAT)}.") }
}

private val SORTS = listOf("A–Z", "Weakest", "Most asked", "Recent")

@Composable
private fun WordsView() {
    var query by rememberSaveable { mutableStateOf("") }
    var sort by rememberSaveable { mutableIntStateOf(0) }
    var expandedId by rememberSaveable { mutableLongStateOf(-1L) }
    val revision = Store.revision
    val shown = remember(query, sort, revision) {
        val q = query.trim().lowercase()
        val filtered = Store.words.filter { q.isEmpty() || q in it.dutch.lowercase() || q in it.german.lowercase() || q in it.note.lowercase() }
        when (sort) {
            1 -> filtered.sortedBy { Logic.average(it.points.takeLast(10)) ?: -1.0 }
            2 -> filtered.sortedByDescending { it.asked }
            3 -> filtered.sortedByDescending { Logic.parseLastAsked(it.lastAsked)?.toEpochSecond(ZoneOffset.UTC) ?: 0L }
            else -> filtered.sortedBy { it.dutch.lowercase() }
        }
    }
    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        SearchField(query, { query = it })
        Spacer(Modifier.height(8.dp))
        Segmented(SORTS, sort, { sort = it }, Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        Hint("${Logic.plural(shown.size, "word")} · tap a word for details")
        Spacer(Modifier.height(6.dp))
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp), contentPadding = PaddingValues(bottom = 16.dp)) {
            items(shown, key = { it.id }) { word ->
                WordStatsRow(word, expanded = word.id == expandedId, onClick = { expandedId = if (expandedId == word.id) -1L else word.id })
            }
        }
    }
}

@Composable
private fun WordStatsRow(word: Word, expanded: Boolean, onClick: () -> Unit) {
    val p = LocalPalette.current
    val average = Logic.average(word.points)
    Panel(Modifier.fillMaxWidth().clickable(onClick = onClick).animateContentSize(), padding = 12) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(word.dutch, color = p.textStrong, fontSize = 15.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                Text(word.german, color = p.textMuted, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Spacer(Modifier.width(10.dp))
            Column(horizontalAlignment = Alignment.End) {
                Text(Logic.scoreLabel(average), color = average?.let { p.scoreColor(it) } ?: p.textSubtle, fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
                Text("${word.asked}× asked", color = p.textSubtle, fontSize = 11.sp)
            }
        }
        if (expanded) {
            Spacer(Modifier.height(8.dp))
            val rows = buildList {
                if (word.note.isNotBlank()) add("Note" to word.note)
                add("Correct / wrong" to "${word.correct} / ${word.wrong}")
                add("Avg last 10" to Logic.scoreLabel(Logic.average(word.points.takeLast(10))))
                add("Avg NL→DE" to Logic.scoreLabel(Logic.average(word.dgPoints)))
                add("Avg DE→NL" to Logic.scoreLabel(Logic.average(word.gdPoints)))
                add("Last 5 scores" to (word.points.takeLast(5).joinToString("  ") { it.roundToInt().toString() }.ifEmpty { "—" }))
                add("Last asked" to word.lastAsked)
            }
            rows.forEach { (label, value) ->
                Row(Modifier.padding(vertical = 2.dp)) {
                    Text(label, color = p.textSubtle, fontSize = 13.sp, modifier = Modifier.weight(1f))
                    Text(value, color = p.textBody, fontSize = 13.sp)
                }
            }
        }
    }
}
