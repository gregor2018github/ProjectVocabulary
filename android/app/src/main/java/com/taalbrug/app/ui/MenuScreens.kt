package com.taalbrug.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.taalbrug.app.Logic
import com.taalbrug.app.Mode
import com.taalbrug.app.R
import com.taalbrug.app.Store

private const val APP_NAME = "Taalbrug"   // Dutch for "language bridge": taal = language, brug = bridge

/** Centered column of buttons with a title block, the layout of the desktop menu screens. */
@Composable
private fun MenuColumn(content: @Composable () -> Unit) {
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp, vertical = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
    ) { content() }
}

private val buttonModifier = Modifier.widthIn(max = 340.dp).fillMaxWidth()

@Composable
private fun TitleBlock(title: @Composable () -> Unit, subtitle: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        title()
        Spacer(Modifier.height(4.dp))
        Hint(subtitle)
    }
    Spacer(Modifier.height(18.dp))
}

@Composable
fun MainMenuScreen(dark: Boolean, onNavigate: (String) -> Unit, onToggleTheme: () -> Unit) {
    val p = LocalPalette.current
    val revision = Store.revision
    val summary = remember(revision) {
        val streak = Logic.currentStreak()
        Logic.plural(Store.words.size, "word") + if (streak > 0) " · ${streak}-day streak" else ""
    }
    MenuColumn {
        Image(painterResource(R.drawable.taalbrug_logo), contentDescription = null, modifier = Modifier.size(96.dp))
        Spacer(Modifier.height(4.dp))
        TitleBlock(
            title = {
                Text(
                    buildAnnotatedString {
                        append(APP_NAME.take(4))
                        withStyle(SpanStyle(fontWeight = FontWeight.SemiBold, color = p.accentText)) { append(APP_NAME.drop(4)) }
                    },
                    color = p.textStrong, fontSize = 34.sp, fontWeight = FontWeight.Light,
                )
            },
            subtitle = "Dutch ↔ German vocabulary trainer",
        )
        AppButton("Start Training", { onNavigate("modes") }, buttonModifier)
        AppButton("Explore Statistics", { onNavigate("stats") }, buttonModifier)
        AppButton("Manage Vocabulary", { onNavigate("manage") }, buttonModifier)
        Spacer(Modifier.height(4.dp))
        AppButton(if (dark) "☀  Light Mode" else "☾  Dark Mode", onToggleTheme, buttonModifier, ButtonVariant.Secondary)
        Spacer(Modifier.height(8.dp))
        Hint(summary)
    }
}

@Composable
fun ModeSelectScreen(onStart: (Mode) -> Unit, onBack: () -> Unit) {
    val p = LocalPalette.current
    MenuColumn {
        TitleBlock(
            title = { Text("Choose a Training Mode", color = p.textStrong, fontSize = 26.sp, fontWeight = FontWeight.SemiBold) },
            subtitle = "Pick the direction you want to practise",
        )
        AppButton("Dutch → German", { onStart(Mode.DG) }, buttonModifier)
        AppButton("German → Dutch", { onStart(Mode.GD) }, buttonModifier)
        AppButton("Random Direction", { onStart(Mode.RA) }, buttonModifier)
        Spacer(Modifier.height(4.dp))
        AppButton("Back", onBack, buttonModifier, ButtonVariant.Secondary)
    }
}
