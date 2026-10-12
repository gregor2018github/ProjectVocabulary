package com.taalbrug.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/** The desktop THEMES palettes (only the tokens the phone UI uses). */
data class Palette(
    val isDark: Boolean,
    val bg: Color, val surface: Color, val surfaceAlt: Color,
    val border: Color, val borderStrong: Color,
    val text: Color, val textStrong: Color, val textBody: Color, val textMuted: Color, val textSubtle: Color,
    val accent: Color, val accentPressed: Color, val accentSoft: Color, val accentText: Color,
    val accentWash: Color, val accentSelect: Color,
    val segmentBg: Color, val segmentChecked: Color,
    val danger: Color, val dangerBorder: Color, val dangerHover: Color,
    val scoreGood: Color, val scoreBad: Color, val scoreMid: Color,
    val chartBlue: Color, val chartRed: Color, val chartGrid: Color, val chartBaseline: Color, val chartLabel: Color, val chartHover: Color,
)

val LightPalette = Palette(
    isDark = false,
    bg = Color(0xFFF4F6FB), surface = Color(0xFFFFFFFF), surfaceAlt = Color(0xFFF9FAFB),
    border = Color(0xFFE3E8EF), borderStrong = Color(0xFFD1D5DB),
    text = Color(0xFF1F2937), textStrong = Color(0xFF111827), textBody = Color(0xFF374151), textMuted = Color(0xFF4B5563), textSubtle = Color(0xFF6B7280),
    accent = Color(0xFF4F46E5), accentPressed = Color(0xFF3730A3), accentSoft = Color(0xFF6366F1), accentText = Color(0xFF4F46E5),
    accentWash = Color(0xFFEEF2FF), accentSelect = Color(0xFFE0E7FF),
    segmentBg = Color(0xFFE9ECF2), segmentChecked = Color(0xFFFFFFFF),
    danger = Color(0xFFDC2626), dangerBorder = Color(0xFFFCA5A5), dangerHover = Color(0xFFFEF2F2),
    scoreGood = Color(0xFF15803D), scoreBad = Color(0xFFB91C1C), scoreMid = Color(0xFFB45309),
    chartBlue = Color(0xFF2A78D6), chartRed = Color(0xFFE34948), chartGrid = Color(0xFFEEF0F3), chartBaseline = Color(0xFFCBD5E1),
    chartLabel = Color(0xFF6B7280), chartHover = Color(0xFFF3F4F6),
)

val DarkPalette = Palette(
    isDark = true,
    bg = Color(0xFF0F1117), surface = Color(0xFF1A1D27), surfaceAlt = Color(0xFF20242F),
    border = Color(0xFF2A2F3C), borderStrong = Color(0xFF3A4050),
    text = Color(0xFFE5E7EB), textStrong = Color(0xFFF3F4F6), textBody = Color(0xFFD1D5DB), textMuted = Color(0xFFA3AAB8), textSubtle = Color(0xFF8B93A3),
    accent = Color(0xFF5B5BD6), accentPressed = Color(0xFF4F46E5), accentSoft = Color(0xFF818CF8), accentText = Color(0xFFA5B4FC),
    accentWash = Color(0xFF262A45), accentSelect = Color(0xFF2E3361),
    segmentBg = Color(0xFF1F2330), segmentChecked = Color(0xFF343A4A),
    danger = Color(0xFFF87171), dangerBorder = Color(0xFF7F1D1D), dangerHover = Color(0xFF2A1618),
    scoreGood = Color(0xFF4ADE80), scoreBad = Color(0xFFF87171), scoreMid = Color(0xFFFBBF24),
    chartBlue = Color(0xFF4A8FE7), chartRed = Color(0xFFEF6461), chartGrid = Color(0xFF262B36), chartBaseline = Color(0xFF3A4050),
    chartLabel = Color(0xFF8B93A3), chartHover = Color(0xFF232835),
)

val LocalPalette = staticCompositionLocalOf { LightPalette }

/** Text color for a score, with the thresholds for correct (> 60) and wrong (< 40). */
fun Palette.scoreColor(points: Double): Color = when {
    points > 60 -> scoreGood
    points < 40 -> scoreBad
    else -> scoreMid
}

@Composable
fun TaalbrugTheme(palette: Palette, content: @Composable () -> Unit) {
    // Material components (text fields, slider, dialogs, menus) take their colors from the palette too
    val base = if (palette.isDark) darkColorScheme() else lightColorScheme()
    val colors = base.copy(
        primary = palette.accent,
        onPrimary = Color.White,
        secondary = palette.accentSoft,
        background = palette.bg,
        onBackground = palette.text,
        surface = palette.surface,
        onSurface = palette.text,
        surfaceVariant = palette.surfaceAlt,
        onSurfaceVariant = palette.textSubtle,
        surfaceContainer = palette.surface,
        surfaceContainerHigh = palette.surface,
        surfaceContainerHighest = palette.surfaceAlt,
        outline = palette.borderStrong,
        outlineVariant = palette.border,
        error = palette.danger,
    )
    CompositionLocalProvider(LocalPalette provides palette) {
        MaterialTheme(colorScheme = colors, content = content)
    }
}
