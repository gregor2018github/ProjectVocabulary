package com.taalbrug.app

import java.time.DayOfWeek
import java.time.Duration
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.temporal.TemporalAdjusters
import kotlin.math.min

/** Training modes as stored in the activity log (no AI mode on the phone). */
enum class Mode(val code: String, val title: String) {
    DG("DG", "Dutch → German"),
    GD("GD", "German → Dutch"),
    RA("RA", "Random"),
}

object Logic {
    private val NEVER = LocalDateTime.of(2000, 1, 1, 0, 0)
    private val DATE_ONLY = DateTimeFormatter.ofPattern("dd/MM/yyyy")

    /** Parse the desktop `last_asked` value ("dd/MM/yyyy HH:mm:ss", older rows "dd/MM/yyyy", or "never"). */
    fun parseLastAsked(value: String): LocalDateTime? = try {
        if (value.length > 10) LocalDateTime.parse(value, Store.LAST_ASKED_FORMAT)
        else LocalDate.parse(value, DATE_ONLY).atStartOfDay()
    } catch (e: Exception) {
        null
    }

    fun average(points: List<Double>): Double? = if (points.isEmpty()) null else points.average()

    /**
     * Choose the word to ask next (port of the desktop `Logic.choose_vocab`).
     * Every word gets its position in three rankings, ascending: when it was last asked, how often it was asked,
     * and its average score over the last 10 answers (weighted twice). Ties are shuffled; the lowest total wins.
     * The last 10 asked words are blocked so nothing repeats too soon (fewer for tiny vocabularies).
     */
    fun chooseWord(words: List<Word>, recentIds: List<Long>): Word? {
        if (words.isEmpty()) return null

        fun <T : Comparable<T>> positions(key: (Word) -> T): Map<Long, Int> {
            val result = HashMap<Long, Int>()
            var position = 0
            words.groupBy(key).toSortedMap().values.forEach { group ->
                group.shuffled().forEach { result[it.id] = position++ }
            }
            return result
        }

        val byLastAsked = positions { (parseLastAsked(it.lastAsked) ?: NEVER).toEpochSecond(ZoneOffset.UTC) }
        val byAsked = positions { it.asked }
        val byAverage = positions { average(it.points.takeLast(10)) ?: 0.0 }
        val ranked = words.sortedBy { byLastAsked.getValue(it.id) + byAsked.getValue(it.id) + 2 * byAverage.getValue(it.id) }

        val blocked = recentIds.takeLast(min(10, words.size - 1)).toSet()
        return ranked.first { it.id !in blocked }
    }

    /** Consecutive days with training, ending today (or yesterday if not trained yet today). */
    fun currentStreak(): Int {
        val trainingDays = Store.trainingDays()
        val today = LocalDate.now()
        var streak = 0
        var day = if (today in trainingDays) today else today.minusDays(1)
        while (day in trainingDays) {
            streak++
            day = day.minusDays(1)
        }
        return streak
    }

    fun scoreLabel(points: Double?): String = points?.let { "%.0f".format(it) } ?: "—"

    fun formatDuration(seconds: Long): String {
        val minutes = (seconds + 30) / 60
        return if (minutes < 60) "$minutes min" else "${minutes / 60} h ${minutes % 60} min"
    }

    fun plural(count: Int, word: String) = "$count $word${if (count == 1) "" else "s"}"
}

/** Aggregated activity log for the statistics dashboards (port of `Logic.create_activity_data`). */
class ActivityData(
    val buckets: List<LocalDate>,
    val weekly: Boolean,
    val trained: List<Int>,
    val averagePoints: List<Double?>,
    val added: List<Int>,
    val removed: List<Int>,
    val hours: List<Int>,
    val activeDays: Int,
    val practiceSeconds: Long,
    val streak: Int,
    val totalPoints: Int,
    val directionCounts: Map<String, List<Int>>,
    val directionAverages: Map<String, List<Double?>>,
    val directionRunning: Map<String, List<Double?>>,
    val directionTotals: Map<String, Pair<Int, Int>>,
    val trackingSince: LocalDate?,
) {
    companion object {
        val DIRECTIONS = listOf("DG", "GD")

        /** The last [days] days; ranges longer than 90 days are bucketed by week (starting Monday). */
        fun create(days: Int): ActivityData {
            val today = LocalDate.now()
            val start = today.minusDays(days - 1L)
            val weekly = days > 90
            fun bucketOf(day: LocalDate) = if (weekly) day.with(TemporalAdjusters.previousOrSame(DayOfWeek.MONDAY)) else day

            val buckets = generateSequence(bucketOf(start)) { it.plusDays(if (weekly) 7 else 1) }.takeWhile { !it.isAfter(today) }.toList()
            val index = buckets.withIndex().associate { (i, bucket) -> bucket to i }
            val n = buckets.size

            val trained = IntArray(n)
            val pointsSum = IntArray(n)
            val added = IntArray(n)
            val removed = IntArray(n)
            val hours = IntArray(24)
            val activeDays = HashSet<LocalDate>()
            val trainedTimes = ArrayList<LocalDateTime>()
            val directionCounts = DIRECTIONS.associateWith { IntArray(n) }
            val directionSums = DIRECTIONS.associateWith { IntArray(n) }

            for (event in Store.loadActivity(start)) {
                val i = index[bucketOf(event.time.toLocalDate())] ?: continue
                activeDays += event.time.toLocalDate()
                when (event.event) {
                    "trained" -> {
                        val points = event.points ?: 0
                        trained[i]++
                        pointsSum[i] += points
                        hours[event.time.hour]++
                        trainedTimes += event.time
                        val direction = event.direction
                        if (direction != null && direction in directionCounts) {
                            directionCounts.getValue(direction)[i]++
                            directionSums.getValue(direction)[i] += points
                        }
                    }
                    "added" -> added[i]++
                    "deleted" -> removed[i]++
                }
            }

            // practice time: sum of the pauses between answers that are at most 5 minutes apart
            val practiceSeconds = trainedTimes.zipWithNext { a, b -> Duration.between(a, b).seconds }.filter { it <= 300 }.sum()

            fun averages(sums: IntArray, counts: IntArray) = List(n) { if (counts[it] > 0) sums[it].toDouble() / counts[it] else null }
            fun runningAverages(sums: IntArray, counts: IntArray): List<Double?> {
                var total = 0
                var count = 0
                return List(n) {
                    total += sums[it]
                    count += counts[it]
                    if (count > 0) total.toDouble() / count else null
                }
            }

            return ActivityData(
                buckets = buckets,
                weekly = weekly,
                trained = trained.toList(),
                averagePoints = averages(pointsSum, trained),
                added = added.toList(),
                removed = removed.toList(),
                hours = hours.toList(),
                activeDays = activeDays.size,
                practiceSeconds = practiceSeconds,
                streak = Logic.currentStreak(),
                totalPoints = pointsSum.sum(),
                directionCounts = directionCounts.mapValues { it.value.toList() },
                directionAverages = DIRECTIONS.associateWith { averages(directionSums.getValue(it), directionCounts.getValue(it)) },
                directionRunning = DIRECTIONS.associateWith { runningAverages(directionSums.getValue(it), directionCounts.getValue(it)) },
                directionTotals = DIRECTIONS.associateWith { directionSums.getValue(it).sum() to directionCounts.getValue(it).sum() },
                trackingSince = Store.firstActivityDate(),
            )
        }
    }
}
