package com.taalbrug.app.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow

/**
 * Panel with a title, a legend and a chart. Tapping or dragging across the chart selects a column,
 * whose details replace the subtitle (the phone stand-in for the desktop hover tooltips).
 */
@Composable
fun ChartPanel(
    title: String,
    subtitle: String,
    details: List<String>,
    legend: List<Pair<String, Color>> = emptyList(),
    chart: @Composable (selected: Int?, onSelect: (Int?) -> Unit) -> Unit,
) {
    val p = LocalPalette.current
    var selected by remember(details) { mutableStateOf<Int?>(null) }
    Panel(Modifier.fillMaxWidth()) {
        Text(title, color = p.textStrong, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
        val caption = selected?.let { details.getOrNull(it)?.replace("\n", " · ") } ?: subtitle
        Text(caption, color = if (selected != null) p.text else p.textSubtle, fontSize = 12.sp, minLines = 2, maxLines = 2)
        if (legend.isNotEmpty()) {
            Spacer(Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                legend.forEach { (name, color) ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(10.dp).clip(RoundedCornerShape(3.dp)).background(color))
                        Spacer(Modifier.width(6.dp))
                        Text(name, color = p.textMuted, fontSize = 12.sp)
                    }
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        chart(selected) { selected = it }
    }
}

private const val LEFT = 30f   // dp for the y labels
private const val TOP = 8f
private const val RIGHT = 4f
private const val BOTTOM = 22f // dp for the x labels

/** A 1/2/5 * 10^n step that splits maxValue into about `ticks` gridlines. */
private fun niceStep(maxValue: Double, ticks: Int = 4): Int {
    val raw = max(maxValue / ticks, 1.0)
    val magnitude = 10.0.pow(floor(log10(raw)))
    for (multiple in listOf(1, 2, 5, 10)) if (raw <= multiple * magnitude) return (multiple * magnitude).toInt()
    return (10 * magnitude).toInt()
}

private fun Modifier.selectable(count: Int, onSelect: (Int?) -> Unit): Modifier {
    fun slotAt(x: Float, width: Float, density: Float): Int? {
        val left = LEFT * density
        val slot = (width - left - RIGHT * density) / max(count, 1)
        val i = floor((x - left) / slot).toInt()
        return if (i in 0 until count) i else null
    }
    return this
        .pointerInput(count) {
            detectTapGestures { onSelect(slotAt(it.x, size.width.toFloat(), density)) }
        }
        .pointerInput(count) {
            detectHorizontalDragGestures { change, _ -> onSelect(slotAt(change.position.x, size.width.toFloat(), density)) }
        }
}

private class PlotArea(val rect: Rect, val slot: Float)

private fun DrawScope.plotArea(count: Int): PlotArea {
    val rect = Rect(LEFT.dp.toPx(), TOP.dp.toPx(), size.width - RIGHT.dp.toPx(), size.height - BOTTOM.dp.toPx())
    return PlotArea(rect, rect.width / max(count, 1))
}

private fun DrawScope.yLabel(measurer: TextMeasurer, text: String, y: Float, plot: Rect, color: Color) {
    val layout = measurer.measure(text, TextStyle(fontSize = 10.sp, color = color))
    drawText(layout, topLeft = Offset(plot.left - 6.dp.toPx() - layout.size.width, y - layout.size.height / 2f))
}

/** Only every n-th x label, so that they never collide. */
private fun DrawScope.xLabels(measurer: TextMeasurer, labels: List<String>, area: PlotArea, color: Color) {
    val style = TextStyle(fontSize = 10.sp, color = color)
    val layouts = labels.map { measurer.measure(it, style) }
    val labelWidth = (layouts.maxOfOrNull { it.size.width } ?: 0) + 10.dp.toPx()
    val every = max(1, ceil(labelWidth / area.slot).toInt())
    for (i in labels.indices step every) {
        val center = area.rect.left + (i + 0.5f) * area.slot
        drawText(layouts[i], topLeft = Offset(center - layouts[i].size.width / 2f, area.rect.bottom + 5.dp.toPx()))
    }
}

private fun DrawScope.emptyText(measurer: TextMeasurer, text: String, plot: Rect, color: Color) {
    val layout = measurer.measure(text, TextStyle(fontSize = 13.sp, color = color))
    drawText(layout, topLeft = Offset(plot.center.x - layout.size.width / 2f, plot.center.y - layout.size.height / 2f))
}

/** A bar with a rounded data end and a square end at the baseline. */
private fun barPath(x: Float, baselineY: Float, width: Float, height: Float, upwards: Boolean, radius: Float): Path {
    val r = min(radius, min(width / 2, height))
    val top = if (upwards) baselineY - height else baselineY
    val corner = CornerRadius(r, r)
    return Path().apply {
        addRoundRect(
            if (upwards) RoundRect(x, top, x + width, top + height, topLeftCornerRadius = corner, topRightCornerRadius = corner)
            else RoundRect(x, top, x + width, top + height, bottomLeftCornerRadius = corner, bottomRightCornerRadius = corner)
        )
    }
}

/**
 * Column chart: one series grows up from the baseline, an optional second one grows down from it
 * (e.g. words added vs. removed).
 */
@Composable
fun BarChart(
    labels: List<String>,
    up: List<Int>,
    upColor: Color,
    selected: Int?,
    onSelect: (Int?) -> Unit,
    down: List<Int>? = null,
    downColor: Color = upColor,
    emptyText: String = "No data in this period",
    height: Int = 180,
) {
    val p = LocalPalette.current
    val measurer = rememberTextMeasurer()
    val downValues = down ?: List(up.size) { 0 }
    Canvas(Modifier.fillMaxWidth().height(height.dp).selectable(labels.size, onSelect)) {
        val area = plotArea(labels.size)
        val plot = area.rect
        val upMax = up.maxOrNull() ?: 0
        val downMax = downValues.maxOrNull() ?: 0
        val step = niceStep(max(upMax, downMax).toDouble())
        val upTop = (ceil(upMax / step.toDouble()) * step).toInt().takeIf { it > 0 } ?: step
        val downBottom = (ceil(downMax / step.toDouble()) * step).toInt()
        val scale = plot.height / (upTop + downBottom)
        val baselineY = plot.top + upTop * scale

        selected?.let { drawRect(p.chartHover, Offset(plot.left + it * area.slot, plot.top), Size(area.slot, plot.height)) }

        // gridlines and y labels (values below the baseline are labelled as positive counts)
        for (value in -downBottom..upTop step step) {
            val y = baselineY - value * scale
            drawLine(if (value == 0) p.chartBaseline else p.chartGrid, Offset(plot.left, y), Offset(plot.right, y), 1.dp.toPx())
            yLabel(measurer, kotlin.math.abs(value).toString(), y, plot, p.chartLabel)
        }

        // bars: at most 20dp wide, always leaving a gap between neighbours
        val barWidth = max(1f, min(20.dp.toPx(), min(area.slot * 0.7f, area.slot - 2.dp.toPx())))
        val radius = 3.dp.toPx()
        for (i in up.indices) {
            val x = plot.left + i * area.slot + (area.slot - barWidth) / 2
            val gap = if (up[i] > 0 && downValues[i] > 0) 1.dp.toPx() else 0f
            if (up[i] > 0) drawPath(barPath(x, baselineY - gap, barWidth, up[i] * scale - gap, true, radius), upColor)
            if (downValues[i] > 0) drawPath(barPath(x, baselineY + gap, barWidth, downValues[i] * scale - gap, false, radius), downColor)
        }

        xLabels(measurer, labels, area, p.chartLabel)
        if (up.all { it == 0 } && downValues.all { it == 0 }) emptyText(measurer, emptyText, plot, p.chartLabel)
    }
}

/** Line chart for scores (fixed 0–100 axis); missing values (null) are skipped and the line connects the neighbours. */
@Composable
fun LineChart(
    labels: List<String>,
    series: List<Pair<List<Double?>, Color>>,
    selected: Int?,
    onSelect: (Int?) -> Unit,
    emptyText: String = "No answers in this period",
    height: Int = 200,
) {
    val p = LocalPalette.current
    val measurer = rememberTextMeasurer()
    Canvas(Modifier.fillMaxWidth().height(height.dp).selectable(labels.size, onSelect)) {
        val area = plotArea(labels.size)
        val plot = area.rect
        val scale = plot.height / 100f

        for (value in 0..100 step 20) {
            val y = plot.bottom - value * scale
            drawLine(if (value == 0) p.chartBaseline else p.chartGrid, Offset(plot.left, y), Offset(plot.right, y), 1.dp.toPx())
            yLabel(measurer, value.toString(), y, plot, p.chartLabel)
        }

        selected?.let {
            val x = plot.left + (it + 0.5f) * area.slot
            drawLine(p.chartBaseline, Offset(x, plot.top), Offset(x, plot.bottom), 1.dp.toPx())
        }

        // lines, then markers with a surface ring; markers on every point only if there is room
        val showAllMarkers = area.slot >= 12.dp.toPx()
        for ((values, color) in series) {
            val points = values.withIndex().mapNotNull { (i, v) ->
                v?.let { i to Offset(plot.left + (i + 0.5f) * area.slot, plot.bottom - it.toFloat() * scale) }
            }
            if (points.size > 1) {
                val path = Path().apply {
                    moveTo(points[0].second.x, points[0].second.y)
                    points.drop(1).forEach { lineTo(it.second.x, it.second.y) }
                }
                drawPath(path, color, style = Stroke(2.dp.toPx(), cap = StrokeCap.Round, join = StrokeJoin.Round))
            }
            for ((i, point) in points) {
                if (showAllMarkers || points.size == 1 || i == selected) {
                    val radius = (if (i == selected) 5 else 4).dp.toPx()
                    drawCircle(p.surface, radius + 2.dp.toPx(), point)
                    drawCircle(color, radius, point)
                }
            }
        }

        xLabels(measurer, labels, area, p.chartLabel)
        if (series.all { (values, _) -> values.all { it == null } }) emptyText(measurer, emptyText, plot, p.chartLabel)
    }
}
