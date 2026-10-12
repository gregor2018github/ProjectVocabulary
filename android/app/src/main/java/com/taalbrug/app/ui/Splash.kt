package com.taalbrug.app.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathMeasure
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.sin

/*
 * Animated brand intro (port of the desktop SplashOverlay). Two flash cards ("brug" / "Brücke") fly in,
 * a bridge arc is drawn between them and a spark crosses it, then the wordmark appears letter by letter.
 * Afterwards the overlay fades out and reveals the main menu underneath. A tap skips it.
 * Drawn in the desktop's pixel units, scaled down to fit narrow phone screens.
 */
private const val CARD_WIDTH = 150f
private const val CARD_HEIGHT = 190f
private const val CARDS_END = 750f           // ms: cards have landed
private val BRIDGE = 550f to 1250f           // ms: bridge arc is drawn
private val SPARK = 1150f to 1850f           // ms: spark travels across the bridge
private const val WORDMARK_START = 1250f     // ms: first letter of the wordmark starts to appear
private val TAGLINE = 2000f to 2450f         // ms: tagline fades in
private const val HOLD_UNTIL = 4300L         // ms: start fading out (complete logo stays ~1.8 s)
private const val FADE_DURATION = 900        // ms
private const val DESIGN_WIDTH = 440f        // units that must fit the screen width

private const val APP_NAME = "Taalbrug"
private const val APP_TAGLINE = "Your bridge from Dutch to German"

private fun progress(elapsed: Float, start: Float, end: Float) = ((elapsed - start) / (end - start)).coerceIn(0f, 1f)
private fun easeOutCubic(t: Float) = 1 - (1 - t).pow(3)
private fun easeOutBack(t: Float): Float {
    val c1 = 1.4f
    return 1 + (c1 + 1) * (t - 1).pow(3) + c1 * (t - 1).pow(2)
}

/** Top-center point of a card rotated by angle around its center. */
private fun cardTop(center: Offset, angle: Float): Offset {
    val radians = Math.toRadians(angle.toDouble())
    val dy = -CARD_HEIGHT / 2 - 8
    return Offset(center.x - dy * sin(radians).toFloat(), center.y + dy * cos(radians).toFloat())
}

@Composable
fun SplashOverlay(onFinished: () -> Unit) {
    val measurer = rememberTextMeasurer()
    var elapsed by remember { mutableFloatStateOf(0f) }
    var fading by remember { mutableStateOf(false) }
    val alpha = remember { Animatable(1f) }

    LaunchedEffect(Unit) {
        val start = withFrameMillis { it }
        while (true) {
            elapsed = (withFrameMillis { it } - start).toFloat()
            if (elapsed >= HOLD_UNTIL) fading = true
            if (alpha.value == 0f) break
        }
    }
    LaunchedEffect(fading) {
        if (fading) {
            alpha.animateTo(0f, tween(FADE_DURATION, easing = FastOutSlowInEasing))
            onFinished()
        }
    }

    Canvas(
        Modifier
            .fillMaxSize()
            .graphicsLayer { this.alpha = alpha.value }
            .pointerInput(Unit) { detectTapGestures { fading = true } }
    ) {
        drawSplash(elapsed, measurer)
    }
}

private fun DrawScope.drawSplash(t: Float, measurer: TextMeasurer) {
    // background: deep indigo gradient over the whole screen
    drawRect(Brush.linearGradient(listOf(Color(0xFF1E1B4B), Color(0xFF3730A3)), Offset.Zero, Offset(size.width, size.height)))

    // design units: origin at the screen center, 1 unit = 1 desktop pixel, shrunk to fit the width
    val scale = min(density, size.width / DESIGN_WIDTH)
    val halfWidth = size.width / scale / 2
    val cx = 0f
    val cy = -60f

    withTransform({
        translate(size.width / 2, size.height / 2)
        scale(scale, scale, pivot = Offset.Zero)
    }) {
        // soft glow that grows behind the logo
        val glowRadius = 160 + 220 * easeOutCubic(progress(t, 0f, 1500f))
        drawCircle(
            Brush.radialGradient(listOf(Color(129, 140, 248, 90), Color(129, 140, 248, 0)), Offset(cx, cy), glowRadius),
            glowRadius, Offset(cx, cy),
        )

        // cards fly in from both sides and settle slightly tilted
        val landing = progress(t, 0f, CARDS_END)
        val travel = easeOutBack(landing)
        val offset = 110 + (1 - travel) * halfWidth
        val leftCenter = Offset(cx - offset, cy)
        val leftAngle = -8 - 22 * (1 - travel)
        val rightCenter = Offset(cx + offset, cy)
        val rightAngle = 8 + 22 * (1 - travel)
        val cardOpacity = min(landing * 2, 1f)
        drawCard(measurer, leftCenter, leftAngle, "NL", "brug", cardOpacity)
        drawCard(measurer, rightCenter, rightAngle, "DE", "Brücke", cardOpacity)

        // bridge arc between the card tops, drawn progressively
        val start = cardTop(leftCenter, leftAngle)
        val end = cardTop(rightCenter, rightAngle)
        val arc = Path().apply {
            moveTo(start.x, start.y)
            quadraticTo(cx, min(start.y, end.y) - 120, end.x, end.y)
        }
        val measure = PathMeasure().apply { setPath(arc, false) }
        val drawn = easeOutCubic(progress(t, BRIDGE.first, BRIDGE.second))
        if (drawn > 0) {
            val segment = Path()
            measure.getSegment(0f, measure.length * drawn, segment, true)
            drawPath(segment, Color(0xFFA5B4FC), style = Stroke(5f, cap = StrokeCap.Round))
        }

        // spark crosses the bridge (a word travelling from Dutch to German)
        val spark = progress(t, SPARK.first, SPARK.second)
        if (spark > 0 && spark < 1) {
            val position = measure.getPosition(measure.length * easeOutCubic(spark))
            val fade = sin(spark * PI).toFloat()
            drawCircle(
                Brush.radialGradient(listOf(Color(251, 191, 36, (200 * fade).toInt()), Color(251, 191, 36, 0)), position, 22f),
                22f, position,
            )
            drawCircle(Color(255, 236, 179, (255 * fade).toInt()), 5f, position)
        }

        // wordmark "Taalbrug", letter by letter: "Taal" light, "brug" bold in the accent color
        val letters = APP_NAME.mapIndexed { i, letter ->
            measurer.measure(
                letter.toString(),
                TextStyle(fontSize = 64f.toSp(), fontWeight = if (i < 4) FontWeight.Light else FontWeight.Bold),
            )
        }
        var x = cx - letters.sumOf { it.size.width } / 2f
        val baseline = cy + CARD_HEIGHT / 2 + 110
        letters.forEachIndexed { i, layout ->
            val begin = WORDMARK_START + i * 70
            val appear = easeOutCubic(progress(t, begin, begin + 380))
            if (appear > 0) {
                drawText(
                    layout,
                    color = if (i < 4) Color.White else Color(0xFFA5B4FC),
                    topLeft = Offset(x, baseline + 18 * (1 - appear) - layout.firstBaseline),
                    alpha = appear,
                )
            }
            x += layout.size.width
        }

        // tagline
        val tagline = progress(t, TAGLINE.first, TAGLINE.second)
        if (tagline > 0) {
            val layout = measurer.measure(APP_TAGLINE, TextStyle(fontSize = 17f.toSp()))
            drawText(layout, color = Color(0xFFC7D2FE), topLeft = Offset(cx - layout.size.width / 2f, baseline + 26), alpha = tagline)
        }
    }
}

private fun DrawScope.drawCard(measurer: TextMeasurer, center: Offset, angle: Float, language: String, word: String, opacity: Float) {
    if (opacity <= 0f) return
    val w = CARD_WIDTH
    val h = CARD_HEIGHT
    translate(center.x, center.y) {
        rotate(angle, pivot = Offset.Zero) {
            val corner = CornerRadius(18f, 18f)
            drawRoundRect(Color(0, 0, 0, 70), Offset(-w / 2 + 4, -h / 2 + 12), Size(w, h), corner, alpha = opacity)  // shadow
            drawRoundRect(Color.White, Offset(-w / 2, -h / 2), Size(w, h), corner, alpha = opacity)
            val label = measurer.measure(language, TextStyle(fontSize = 13f.toSp(), fontWeight = FontWeight.Bold))
            drawText(label, color = Color(0xFF6366F1), topLeft = Offset(-w / 2 + 16, -h / 2 + 12), alpha = opacity)
            val text = measurer.measure(word, TextStyle(fontSize = 26f.toSp(), fontWeight = FontWeight.SemiBold))
            drawText(text, color = Color(0xFF111827), topLeft = Offset(-text.size.width / 2f, -text.size.height / 2f), alpha = opacity)
        }
    }
}
