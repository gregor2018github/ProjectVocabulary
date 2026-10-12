package com.taalbrug.app.ui

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Slider
import androidx.compose.material3.SliderDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.taalbrug.app.Logic
import com.taalbrug.app.Mode
import com.taalbrug.app.Store
import com.taalbrug.app.Word
import kotlin.math.roundToInt
import kotlin.random.Random

private class CardFace(val language: String, val text: String, val note: String = "")

/**
 * One word at a time: tap the card to flip it, rate how well you knew it, then "Next Vocabulary".
 * In random mode the direction is drawn per word and fixed by the side shown first.
 */
@Composable
fun TrainingScreen(mode: Mode, onEnd: () -> Unit) {
    val p = LocalPalette.current
    var wordId by rememberSaveable { mutableLongStateOf(-1L) }
    var dutchFirst by rememberSaveable { mutableStateOf(true) }
    var flipped by rememberSaveable { mutableStateOf(false) }
    var revealed by rememberSaveable { mutableStateOf(false) }
    var rating by rememberSaveable { mutableFloatStateOf(50f) }
    var answered by rememberSaveable { mutableIntStateOf(0) }

    fun nextWord() {
        val word = Logic.chooseWord(Store.words, Store.sessionIds) ?: return
        Store.sessionIds += word.id
        wordId = word.id
        dutchFirst = when (mode) {
            Mode.DG -> true
            Mode.GD -> false
            Mode.RA -> Random.nextBoolean()
        }
        flipped = false
        revealed = false
        rating = 50f
    }

    if (wordId == -1L) nextWord()
    val word: Word? = Store.words.find { it.id == wordId }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        // header: mode hint on the left, a small red "End" button on the right
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                val direction = if (dutchFirst) "Dutch → German" else "German → Dutch"
                Text(if (mode == Mode.RA) "Random · $direction" else direction, color = p.textStrong, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                Hint(if (answered == 0) "Tap the card to flip it" else "${Logic.plural(answered, "word")} trained this session")
            }
            AppButton("End Training", onEnd, variant = ButtonVariant.Danger, height = 36)
        }

        if (word == null) {
            Spacer(Modifier.weight(1f))
            Hint("No vocabulary yet. Add words in Manage Vocabulary.", Modifier.fillMaxWidth(), TextAlign.Center)
            Spacer(Modifier.weight(1f))
            return@Column
        }

        val dutch = CardFace("NEDERLANDS", word.dutch, word.note)
        val german = CardFace("DEUTSCH", word.german)
        Spacer(Modifier.weight(1f))
        // a new key per word, so the next card starts unflipped instead of animating back over the answer
        key(wordId) {
            FlipCard(
                front = if (dutchFirst) dutch else german,
                back = if (dutchFirst) german else dutch,
                flipped = flipped,
                onClick = {
                    flipped = !flipped
                    revealed = true
                },
                modifier = Modifier.fillMaxWidth().height(320.dp),
            )
        }
        Spacer(Modifier.height(20.dp))

        // rating and "Next Vocabulary": laid out from the start (invisible) so the card never moves
        Column(Modifier.fillMaxWidth().alpha(if (revealed) 1f else 0f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Hint("How well did you know it?", Modifier.weight(1f))
                Text(rating.roundToInt().toString(), color = p.scoreColor(rating.roundToInt().toDouble()), fontSize = 22.sp, fontWeight = FontWeight.SemiBold)
            }
            Slider(
                value = rating,
                onValueChange = { rating = it },
                valueRange = 0f..100f,
                enabled = revealed,
                colors = SliderDefaults.colors(thumbColor = p.accent, activeTrackColor = p.accent, inactiveTrackColor = p.segmentBg),
            )
            Row {
                Hint("Not at all", Modifier.weight(1f))
                Hint("Knew it perfectly")
            }
            Spacer(Modifier.height(14.dp))
            AppButton(
                "Next Vocabulary",
                onClick = {
                    Store.recordAnswer(word, rating.roundToInt(), mode.code, if (dutchFirst) "DG" else "GD")
                    answered++
                    nextWord()
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = revealed,
            )
        }
        Spacer(Modifier.weight(1f))
    }
}

@Composable
private fun FlipCard(front: CardFace, back: CardFace, flipped: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val p = LocalPalette.current
    val rotation by animateFloatAsState(
        if (flipped) 180f else 0f, animationSpec = tween(450, easing = FastOutSlowInEasing), label = "flip",
    )
    val shape = RoundedCornerShape(14.dp)
    Box(
        modifier
            .graphicsLayer {
                rotationY = rotation
                cameraDistance = 16f * density
            }
            .clip(shape)
            .background(p.surface)
            .border(1.dp, if (flipped) p.accentSoft else p.border, shape)
            .clickable(interactionSource = remember { MutableInteractionSource() }, indication = null, onClick = onClick),
    ) {
        // past 90° the back face shows; it is mirrored once more so its text reads normally
        val showBack = rotation > 90f
        val face = if (showBack) back else front
        Box(Modifier.fillMaxSize().graphicsLayer { if (showBack) rotationY = 180f }.padding(20.dp)) {
            Text(face.language, color = p.accentSoft, fontSize = 12.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
            Column(
                Modifier.fillMaxSize(),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                val size = when {
                    face.text.length > 80 -> 20.sp
                    face.text.length > 36 -> 24.sp
                    else -> 30.sp
                }
                Text(face.text, color = p.textStrong, fontSize = size, lineHeight = size * 1.25f, fontWeight = FontWeight.Light, textAlign = TextAlign.Center)
                if (face.note.isNotBlank()) {
                    Spacer(Modifier.height(10.dp))
                    Text(face.note, color = p.textSubtle, fontSize = 17.sp, textAlign = TextAlign.Center)
                }
            }
        }
    }
}
