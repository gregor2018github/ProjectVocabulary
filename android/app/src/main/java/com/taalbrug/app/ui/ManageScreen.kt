package com.taalbrug.app.ui

import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.taalbrug.app.Logic
import com.taalbrug.app.Store
import com.taalbrug.app.Word

private const val NEW_WORD = 0L     // editingId value for the "add" dialog
private const val NO_DIALOG = -1L

/** Add, edit and delete words; the menu moves the whole database between phone and PC. */
@Composable
fun ManageScreen(onBack: () -> Unit) {
    val p = LocalPalette.current
    val context = LocalContext.current
    var query by rememberSaveable { mutableStateOf("") }
    var editingId by rememberSaveable { mutableLongStateOf(NO_DIALOG) }
    var menuOpen by remember { mutableStateOf(false) }
    var confirmImport by remember { mutableStateOf(false) }
    val revision = Store.revision
    val shown = remember(query, revision) {
        val q = query.trim().lowercase()
        Store.words.filter { q.isEmpty() || q in it.dutch.lowercase() || q in it.german.lowercase() || q in it.note.lowercase() }
    }

    val exportLauncher = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("application/octet-stream")) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        val ok = runCatching { context.contentResolver.openOutputStream(uri)!!.use { Store.exportTo(it) } }.isSuccess
        Toast.makeText(context, if (ok) "Database exported" else "Export failed", Toast.LENGTH_SHORT).show()
    }
    val importLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        val error = runCatching { Store.importFrom(context.contentResolver.openInputStream(uri)!!) }.getOrElse { "Import failed" }
        Toast.makeText(context, error ?: "Imported ${Logic.plural(Store.words.size, "word")}", Toast.LENGTH_LONG).show()
    }

    Box(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize()) {
            ScreenHeader("Manage Vocabulary", "${Logic.plural(Store.words.size, "word")} · tap a word to edit it", {
                Store.sessionIds.clear()  // reset the session when leaving vocabulary management
                onBack()
            }) {
                Box {
                    IconButton(onClick = { menuOpen = true }) { Icon(Icons.Default.MoreVert, contentDescription = "More", tint = p.text) }
                    DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
                        DropdownMenuItem(text = { Text("Export database…") }, onClick = {
                            menuOpen = false
                            exportLauncher.launch("vocabulary.db")
                        })
                        DropdownMenuItem(text = { Text("Import database…") }, onClick = {
                            menuOpen = false
                            confirmImport = true
                        })
                    }
                }
            }
            SearchField(query, { query = it }, Modifier.padding(horizontal = 16.dp))
            Spacer(Modifier.height(10.dp))
            LazyColumn(
                Modifier.padding(horizontal = 16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
                contentPadding = PaddingValues(bottom = 88.dp),  // room for the add button
            ) {
                items(shown, key = { it.id }) { word ->
                    Panel(Modifier.fillMaxWidth().clickable { editingId = word.id }, padding = 12) {
                        Text(word.dutch, color = p.textStrong, fontSize = 15.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        Text(word.german, color = p.textMuted, fontSize = 14.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        if (word.note.isNotBlank()) Text(word.note, color = p.textSubtle, fontSize = 12.sp, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
        }
        ExtendedFloatingActionButton(
            onClick = { editingId = NEW_WORD },
            icon = { Icon(Icons.Default.Add, contentDescription = null) },
            text = { Text("Add Word") },
            containerColor = p.accent,
            contentColor = Color.White,
            modifier = Modifier.align(Alignment.BottomEnd).padding(16.dp),
        )
    }

    if (editingId != NO_DIALOG) {
        val word = Store.words.find { it.id == editingId }
        WordDialog(word, onDismiss = { editingId = NO_DIALOG })
    }

    if (confirmImport) {
        AlertDialog(
            onDismissRequest = { confirmImport = false },
            title = { Text("Import database?") },
            text = { Text("All words and training stats on this phone are replaced by the imported file (e.g. vocabulary.db from the PC app). Export first if you want to keep them.") },
            confirmButton = {
                TextButton(onClick = {
                    confirmImport = false
                    importLauncher.launch(arrayOf("*/*"))
                }) { Text("Choose file") }
            },
            dismissButton = { TextButton(onClick = { confirmImport = false }) { Text("Cancel") } },
        )
    }
}

/** Add (word == null) or edit a word; editing also offers deleting it after a confirmation. */
@Composable
private fun WordDialog(word: Word?, onDismiss: () -> Unit) {
    val p = LocalPalette.current
    var dutch by rememberSaveable { mutableStateOf(word?.dutch ?: "") }
    var german by rememberSaveable { mutableStateOf(word?.german ?: "") }
    var note by rememberSaveable { mutableStateOf(word?.note ?: "") }
    var confirmDelete by remember { mutableStateOf(false) }
    val valid = dutch.isNotBlank() && german.isNotBlank()

    if (confirmDelete && word != null) {
        AlertDialog(
            onDismissRequest = { confirmDelete = false },
            title = { Text("Delete word?") },
            text = { Text("Delete '${word.dutch}' and all its training stats? This cannot be undone.") },
            confirmButton = {
                TextButton(onClick = {
                    Store.deleteWord(word)
                    onDismiss()
                }) { Text("Delete", color = p.danger) }
            },
            dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
        )
        return
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = p.surface,
        title = { Text(if (word == null) "Add Word" else "Edit Word", color = p.textStrong) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                WordField("Dutch", dutch) { dutch = it }
                WordField("German", german) { german = it }
                WordField("Note", note, ImeAction.Done) { note = it }
                if (word != null) {
                    AppButton("Delete Word", { confirmDelete = true }, Modifier.fillMaxWidth(), ButtonVariant.Danger, height = 44)
                }
            }
        },
        confirmButton = {
            TextButton(enabled = valid, onClick = {
                if (word == null) Store.addWord(dutch.trim(), german.trim(), note.trim())
                else Store.updateWord(word, dutch.trim(), german.trim(), note.trim())
                onDismiss()
            }) { Text(if (word == null) "Add" else "Save") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancel") } },
    )
}

@Composable
private fun WordField(label: String, value: String, imeAction: ImeAction = ImeAction.Next, onValueChange: (String) -> Unit) {
    val p = LocalPalette.current
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        label = { Text(label) },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.None, imeAction = imeAction),
        colors = OutlinedTextFieldDefaults.colors(unfocusedBorderColor = p.border, focusedBorderColor = p.accent),
    )
}
