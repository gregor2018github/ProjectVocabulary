package com.taalbrug.app

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

/** One vocabulary row; the stats fields mirror the desktop app's `vocabulary` table. */
class Word(
    val id: Long,
    var dutch: String,
    var german: String,
    var note: String,
    var asked: Int = 0,
    var correct: Int = 0,
    var wrong: Int = 0,
    val points: MutableList<Double> = mutableListOf(),
    val dgPoints: MutableList<Double> = mutableListOf(),
    val gdPoints: MutableList<Double> = mutableListOf(),
    var lastAsked: String = "never",
)

/** A row of the activity log: (time, event, points, direction). */
data class ActivityEvent(val time: LocalDateTime, val event: String, val points: Int?, val direction: String?)

/**
 * The SQLite file uses exactly the desktop schema, so `files/vocabulary.db` can be copied between the
 * PC and the phone. WAL is off so the single .db file is always complete for export.
 */
private class VocabDatabase(context: Context) : SQLiteOpenHelper(context, Store.DB_NAME, null, 1) {
    init {
        setWriteAheadLoggingEnabled(false)
    }

    // a desktop database has user_version 0, so onCreate also runs on it: every statement must be idempotent
    override fun onCreate(db: SQLiteDatabase) = ensureSchema(db)

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = ensureSchema(db)

    override fun onOpen(db: SQLiteDatabase) {
        if (!db.isReadOnly) ensureSchema(db)
    }

    private fun ensureSchema(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS vocabulary (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                dutch       TEXT    NOT NULL,
                german      TEXT    NOT NULL,
                note        TEXT    DEFAULT '',
                asked       INTEGER DEFAULT 0,
                correct     INTEGER DEFAULT 0,
                wrong       INTEGER DEFAULT 0,
                points      TEXT    DEFAULT '[]',
                d_g_points  TEXT    DEFAULT '[]',
                g_d_points  TEXT    DEFAULT '[]',
                last_asked  TEXT    DEFAULT 'never'
            )"""
        )
        db.execSQL(
            """CREATE TABLE IF NOT EXISTS activity_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                event       TEXT    NOT NULL,
                vocab_id    INTEGER,
                mode        TEXT,
                points      INTEGER,
                direction   TEXT
            )"""
        )
        db.rawQuery("PRAGMA table_info(activity_log)", null).use { cursor ->
            val columns = generateSequence { if (cursor.moveToNext()) cursor.getString(1) else null }.toList()
            if ("direction" !in columns) db.execSQL("ALTER TABLE activity_log ADD COLUMN direction TEXT")
        }
        db.execSQL("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    }
}

/** Vocabulary state and persistence (the counterpart of the desktop `Data` class). */
object Store {
    const val DB_NAME = "vocabulary.db"
    val LAST_ASKED_FORMAT: DateTimeFormatter = DateTimeFormatter.ofPattern("dd/MM/yyyy HH:mm:ss")
    private val TIMESTAMP_FORMAT: DateTimeFormatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")

    private lateinit var appContext: Context
    private lateinit var helper: VocabDatabase
    private val db: SQLiteDatabase get() = helper.writableDatabase

    val words = mutableListOf<Word>()
    /** ids of the words asked in this session, newest last (recent ones are blocked from repeating) */
    val sessionIds = mutableListOf<Long>()
    /** bumped after every change so screens re-read the data */
    var revision by mutableIntStateOf(0)
        private set

    val isReady: Boolean get() = ::helper.isInitialized

    fun init(context: Context) {
        appContext = context.applicationContext
        val file = appContext.getDatabasePath(DB_NAME)
        var seeded = file.exists()
        if (!seeded) seeded = copySeedFromAssets(file)
        helper = VocabDatabase(appContext)
        if (!seeded) insertExamples()
        load()
    }

    /** First launch: start from the desktop database bundled at build time, if there is one. */
    private fun copySeedFromAssets(target: File): Boolean = try {
        target.parentFile?.mkdirs()
        appContext.assets.open(DB_NAME).use { input -> target.outputStream().use { input.copyTo(it) } }
        true
    } catch (e: java.io.IOException) {
        false
    }

    private fun insertExamples() {
        for ((dutch, german, note) in listOf(Triple("hallo", "hallo", "ha-lo"), Triple("de kat", "die Katze", ""), Triple("het huis", "das Haus", ""))) {
            db.insert("vocabulary", null, ContentValues().apply { put("dutch", dutch); put("german", german); put("note", note) })
        }
    }

    private fun parsePoints(json: String?): MutableList<Double> {
        val array = JSONArray(json ?: "[]")
        return MutableList(array.length()) { array.getDouble(it) }
    }

    /** Whole numbers are written as ints, like the desktop app does. */
    private fun pointsJson(points: List<Double>): String =
        points.joinToString(", ", "[", "]") { if (it % 1.0 == 0.0) it.toLong().toString() else it.toString() }

    fun load() {
        words.clear()
        db.rawQuery(
            "SELECT id, dutch, german, note, asked, correct, wrong, points, d_g_points, g_d_points, last_asked FROM vocabulary ORDER BY id",
            null
        ).use { c ->
            while (c.moveToNext()) {
                words += Word(
                    id = c.getLong(0),
                    dutch = c.getString(1) ?: "",
                    german = c.getString(2) ?: "",
                    note = c.getString(3) ?: "",
                    asked = c.getInt(4),
                    correct = c.getInt(5),
                    wrong = c.getInt(6),
                    points = parsePoints(c.getString(7)),
                    dgPoints = parsePoints(c.getString(8)),
                    gdPoints = parsePoints(c.getString(9)),
                    lastAsked = c.getString(10) ?: "never",
                )
            }
        }
        sessionIds.clear()
        revision++
    }

    /** Store a training answer: update the word's stats and log it ('direction' is DG or GD). */
    fun recordAnswer(word: Word, points: Int, mode: String, direction: String) {
        word.asked += 1
        word.lastAsked = LocalDateTime.now().format(LAST_ASKED_FORMAT)
        word.points += points.toDouble()
        (if (direction == "DG") word.dgPoints else word.gdPoints) += points.toDouble()
        if (points > 60) word.correct += 1 else if (points < 40) word.wrong += 1
        db.update("vocabulary", ContentValues().apply {
            put("asked", word.asked)
            put("correct", word.correct)
            put("wrong", word.wrong)
            put("points", pointsJson(word.points))
            put("d_g_points", pointsJson(word.dgPoints))
            put("g_d_points", pointsJson(word.gdPoints))
            put("last_asked", word.lastAsked)
        }, "id = ?", arrayOf(word.id.toString()))
        logActivity("trained", word.id, mode, points, direction)
        revision++
    }

    fun addWord(dutch: String, german: String, note: String) {
        val id = db.insert("vocabulary", null, ContentValues().apply { put("dutch", dutch); put("german", german); put("note", note) })
        logActivity("added", id)
        words += Word(id, dutch, german, note)
        revision++
    }

    fun updateWord(word: Word, dutch: String, german: String, note: String) {
        db.update("vocabulary", ContentValues().apply { put("dutch", dutch); put("german", german); put("note", note) },
            "id = ?", arrayOf(word.id.toString()))
        word.dutch = dutch
        word.german = german
        word.note = note
        revision++
    }

    fun deleteWord(word: Word) {
        db.delete("vocabulary", "id = ?", arrayOf(word.id.toString()))
        logActivity("deleted", word.id)
        words.remove(word)
        sessionIds.removeAll { it == word.id }
        revision++
    }

    fun logActivity(event: String, vocabId: Long? = null, mode: String? = null, points: Int? = null, direction: String? = null) {
        db.insert("activity_log", null, ContentValues().apply {
            put("timestamp", LocalDateTime.now().format(TIMESTAMP_FORMAT))
            put("event", event)
            vocabId?.let { put("vocab_id", it) }
            mode?.let { put("mode", it) }
            points?.let { put("points", it) }
            direction?.let { put("direction", it) }
        })
    }

    fun loadSetting(key: String): String? =
        db.rawQuery("SELECT value FROM settings WHERE key = ?", arrayOf(key)).use { if (it.moveToFirst()) it.getString(0) else null }

    fun saveSetting(key: String, value: String) {
        db.insertWithOnConflict("settings", null, ContentValues().apply { put("key", key); put("value", value) }, SQLiteDatabase.CONFLICT_REPLACE)
    }

    /** All logged events since the given date, oldest first; old rows without a direction take it from the mode. */
    fun loadActivity(since: LocalDate): List<ActivityEvent> =
        db.rawQuery(
            """SELECT timestamp, event, points,
                      COALESCE(direction, CASE mode WHEN 'DG' THEN 'DG' WHEN 'AI' THEN 'DG' WHEN 'GD' THEN 'GD' END)
               FROM activity_log WHERE timestamp >= ? ORDER BY timestamp""",
            arrayOf(since.toString())
        ).use { c ->
            buildList {
                while (c.moveToNext()) {
                    add(ActivityEvent(
                        LocalDateTime.parse(c.getString(0), TIMESTAMP_FORMAT),
                        c.getString(1),
                        if (c.isNull(2)) null else c.getInt(2),
                        c.getString(3),
                    ))
                }
            }
        }

    fun trainingDays(): Set<LocalDate> =
        db.rawQuery("SELECT DISTINCT substr(timestamp, 1, 10) FROM activity_log WHERE event = 'trained'", null).use { c ->
            buildSet { while (c.moveToNext()) add(LocalDate.parse(c.getString(0))) }
        }

    fun firstActivityDate(): LocalDate? =
        db.rawQuery("SELECT MIN(timestamp) FROM activity_log", null).use { c ->
            if (c.moveToFirst() && !c.isNull(0)) LocalDate.parse(c.getString(0).substring(0, 10)) else null
        }

    // ---- moving the database between phone and PC ----

    fun exportTo(output: OutputStream) {
        appContext.getDatabasePath(DB_NAME).inputStream().use { it.copyTo(output) }
    }

    /**
     * Replace the phone's database with an imported desktop/phone database.
     * The file is checked first; on failure the current data stays untouched and an error message is returned.
     */
    fun importFrom(input: InputStream): String? {
        val candidate = File(appContext.cacheDir, "import.db")
        input.use { source -> candidate.outputStream().use { source.copyTo(it) } }
        val error = try {
            SQLiteDatabase.openDatabase(candidate.path, null, SQLiteDatabase.OPEN_READONLY).use { check ->
                check.rawQuery("SELECT COUNT(*) FROM vocabulary", null).use { it.moveToFirst() }
            }
            null
        } catch (e: Exception) {
            "This file is not a Taalbrug database."
        }
        if (error != null) {
            candidate.delete()
            return error
        }
        helper.close()
        val target = appContext.getDatabasePath(DB_NAME)
        for (suffix in listOf("-journal", "-wal", "-shm")) File(target.path + suffix).delete()
        candidate.copyTo(target, overwrite = true)
        candidate.delete()
        helper = VocabDatabase(appContext)
        load()
        return null
    }
}
