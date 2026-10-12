package com.taalbrug.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Clear
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

enum class ButtonVariant { Primary, Secondary, Danger }

@Composable
fun AppButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    variant: ButtonVariant = ButtonVariant.Primary,
    height: Int = 52,
    enabled: Boolean = true,
) {
    val p = LocalPalette.current
    val shape = RoundedCornerShape(10.dp)
    val label: @Composable RowScope.() -> Unit = { Text(text, fontSize = 15.sp, fontWeight = FontWeight.SemiBold) }
    val buttonModifier = modifier.height(height.dp)
    when (variant) {
        ButtonVariant.Primary -> Button(
            onClick = onClick, modifier = buttonModifier, shape = shape, enabled = enabled,
            colors = ButtonDefaults.buttonColors(containerColor = p.accent, contentColor = androidx.compose.ui.graphics.Color.White),
            content = label,
        )
        ButtonVariant.Secondary -> OutlinedButton(
            onClick = onClick, modifier = buttonModifier, shape = shape, enabled = enabled,
            border = BorderStroke(1.dp, p.borderStrong),
            colors = ButtonDefaults.outlinedButtonColors(containerColor = p.surface, contentColor = p.text),
            content = label,
        )
        ButtonVariant.Danger -> OutlinedButton(
            onClick = onClick, modifier = buttonModifier, shape = shape, enabled = enabled,
            border = BorderStroke(1.dp, p.dangerBorder),
            colors = ButtonDefaults.outlinedButtonColors(containerColor = p.surface, contentColor = p.danger),
            contentPadding = if (height < 40) PaddingValues(horizontal = 14.dp) else ButtonDefaults.ContentPadding,
            content = label,
        )
    }
}

/** Header of every screen below the main menu: back arrow, title and subtitle, optional actions on the right. */
@Composable
fun ScreenHeader(title: String, subtitle: String, onBack: () -> Unit, actions: @Composable RowScope.() -> Unit = {}) {
    val p = LocalPalette.current
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth().padding(end = 4.dp, top = 4.dp)) {
        IconButton(onClick = onBack) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = p.text)
        }
        Column(Modifier.weight(1f)) {
            Text(title, color = p.textStrong, fontSize = 22.sp, fontWeight = FontWeight.SemiBold)
            if (subtitle.isNotEmpty()) Text(subtitle, color = p.textSubtle, fontSize = 13.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        actions()
    }
}

@Composable
fun Hint(text: String, modifier: Modifier = Modifier, textAlign: TextAlign? = null) {
    Text(text, color = LocalPalette.current.textSubtle, fontSize = 13.sp, modifier = modifier, textAlign = textAlign)
}

/** White (or dark) rounded panel with a thin border, the desktop `QFrame#panel`. */
@Composable
fun Panel(modifier: Modifier = Modifier, padding: Int = 16, content: @Composable ColumnScope.() -> Unit) {
    val p = LocalPalette.current
    val shape = RoundedCornerShape(14.dp)
    Column(
        modifier
            .clip(shape)
            .background(p.surface)
            .border(1.dp, p.border, shape)
            .padding(padding.dp),
        content = content,
    )
}

/** Segmented control (tabs / range filter). */
@Composable
fun Segmented(options: List<String>, selected: Int, onSelect: (Int) -> Unit, modifier: Modifier = Modifier) {
    val p = LocalPalette.current
    Row(
        modifier
            .clip(RoundedCornerShape(10.dp))
            .background(p.segmentBg)
            .padding(3.dp),
        horizontalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        options.forEachIndexed { index, option ->
            val checked = index == selected
            val shape = RoundedCornerShape(8.dp)
            Box(
                Modifier
                    .weight(1f)
                    .clip(shape)
                    .then(if (checked) Modifier.background(p.segmentChecked).border(1.dp, p.borderStrong, shape) else Modifier)
                    .clickable { onSelect(index) }
                    .padding(vertical = 8.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    option, fontSize = 13.sp, maxLines = 1,
                    color = if (checked) p.textStrong else p.textMuted,
                    fontWeight = if (checked) FontWeight.SemiBold else FontWeight.Medium,
                )
            }
        }
    }
}

@Composable
fun StatTile(label: String, value: String, note: String, modifier: Modifier = Modifier) {
    val p = LocalPalette.current
    Panel(modifier, padding = 14) {
        Text(label, color = p.textSubtle, fontSize = 12.sp, fontWeight = FontWeight.Medium, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(value, color = p.textStrong, fontSize = 24.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
        Text(note, color = p.textSubtle, fontSize = 11.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
fun SearchField(value: String, onValueChange: (String) -> Unit, modifier: Modifier = Modifier) {
    val p = LocalPalette.current
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth(),
        placeholder = { Text("Search words…") },
        singleLine = true,
        leadingIcon = { Icon(Icons.Default.Search, contentDescription = null, tint = p.textSubtle) },
        trailingIcon = {
            if (value.isNotEmpty()) IconButton(onClick = { onValueChange("") }) {
                Icon(Icons.Default.Clear, contentDescription = "Clear search", tint = p.textSubtle)
            }
        },
        shape = RoundedCornerShape(10.dp),
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
        colors = OutlinedTextFieldDefaults.colors(
            focusedContainerColor = p.surface, unfocusedContainerColor = p.surface,
            unfocusedBorderColor = p.border, focusedBorderColor = p.accent,
        ),
    )
}
