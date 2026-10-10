
# IMPORTS

import datetime
import json
import numbers
import os
import sqlite3
from openai import OpenAI
import pandas as pd
import random
import sys
import time
from pygame import mixer
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QHBoxLayout, QWidget, QLabel, QSlider, QTableView, QTableWidget, QTableWidgetItem, QLineEdit, QComboBox, QMessageBox, QHeaderView, QAbstractItemView, QFrame, QGridLayout
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QCoreApplication, QSortFilterProxyModel
import openpyxl

# MODULE IMPORTS

import config

# HELPERS

def score_color(points: float) -> str:
    """Return the text color for a score, matching the thresholds for correct (> 60) and wrong (< 40)."""
    if points > 60:
        return "#15803D"
    if points < 40:
        return "#B91C1C"
    return "#B45309"

# CLASSES

class Table(QAbstractTableModel):
    """A class to create a standard table model for the statistics table"""
    SORT_ROLE = Qt.ItemDataRole.UserRole

    def __init__(self, data: pd.DataFrame, text_columns: tuple = (), score_columns: tuple = (), date_columns: tuple = ()) -> None:
        super().__init__()
        self._data = data
        self._text_columns = {data.columns.get_loc(c) for c in text_columns}
        self._score_columns = {data.columns.get_loc(c) for c in score_columns}
        self._date_columns = {data.columns.get_loc(c) for c in date_columns}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data.columns)

    def _display(self, value, column: int) -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return "—"
        if column in self._date_columns:
            return "never" if value == "never" else str(value).split(" ")[0]
        if isinstance(value, float):
            return f"{value:.0f}"
        return str(value)

    def _sort_key(self, value, column: int):
        if column in self._date_columns:
            for date_format in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
                try:
                    return datetime.datetime.strptime(str(value), date_format).timestamp()
                except ValueError:
                    pass
            return 0.0
        if column in self._text_columns:
            return str(value).lower()
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return -1.0
        if isinstance(value, numbers.Real):
            return float(value)
        return str(value)

    def data(self, index: QModelIndex, role: Qt.ItemDataRole):
        value = self._data.iloc[index.row(), index.column()]
        column = index.column()
        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(value, column)
        if role == Qt.ItemDataRole.ToolTipRole and column in self._text_columns:
            return str(value)
        if role == Table.SORT_ROLE:
            return self._sort_key(value, column)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in self._text_columns:
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter
        if role == Qt.ItemDataRole.ForegroundRole and column in self._score_columns and isinstance(value, numbers.Real) and not pd.isna(value):
            return QColor(score_color(value))
        if role == Qt.ItemDataRole.FontRole and column == 0:
            font = QFont()
            font.setWeight(QFont.Weight.DemiBold)
            return font
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole) -> str | None:
        if orientation != Qt.Orientation.Horizontal:
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self._data.columns[section])
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if section in self._text_columns:
                return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            return Qt.AlignmentFlag.AlignCenter
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

class Data:
    """A class to handle (load, save, manipulate) the data of the vocabulary"""
    data_frame = []         # nested list with all data combined
    id_list = []           # SQLite row IDs, one per word (maps list index → DB id)
    dutch_voc_list = []     # df[0]: dutch word
    german_voc_list = []    # df[1]: german translation of the dutch word
    phonetics_list = []     # df[2]: phonetics of the dutch word
    asked = []              # df[3]: how often was the word asked, one integer per word
    correct = []            # df[4]: how often was the word answered correctly (> 60 points), one integer per word
    wrong = []              # df[5]: how often was the word answered wrong (< 40 points), one integer per word
    points = []             # df[6]: how secure was the trainee with the word, several doubles per word
    d_g_points = []         # df[7]: how secure was the trainee with the word, several doubles per word, only for Dutch->German translations
    g_d_points = []         # df[8]: how secure was the trainee with the word, several doubles per word, only for German->Dutch translations
    last_asked = []         # df[9]: when was the word asked the last time, one date per word
    current_date = []       # df[10]: current date, gets updated every time the program is started
    session_vocabs = []     # temporary storage of what vocabs where asked this session

    def add_current_date() -> None:
        """Add the current date to the current_date list."""
        date = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        Data.current_date.append(date)

    def load_and_check_xlsx(filename: str) -> None:
        """Load vocabulary from an Excel file. Check if the file exists and if it contains the correct columns."""
        print("Loading vocabulary from Excel file...")
        if not os.path.exists(filename):
            raise FileNotFoundError(f"The file {filename} is not found.")
        # Load the Excel file
        workbook = openpyxl.load_workbook(filename)
        sheet = workbook.active

        # Check if the sheet contains the correct columns
        expected_columns = ["DUTCH", "GERMAN", "NOTE"]
        actual_columns = [cell.value for cell in sheet[1]]
        if actual_columns != expected_columns:
            raise ValueError(f"The Excel file must contain the following columns: {expected_columns}, but found: {actual_columns}")
        # Read the data from the sheet
        temp_dutch_voc_list = []
        temp_german_voc_list = []
        temp_phonetics_list = []

        for row in sheet.iter_rows(min_row=2, values_only=True):
            temp_dutch_voc_list.append(row[0])
            temp_german_voc_list.append(row[1])
            # Ensure phonetics is a string, even if the cell is empty
            phonetics_val = row[2] if row[2] is not None else ""
            temp_phonetics_list.append(phonetics_val)

        # when there is no json file, then save the lists as the DataHandler lists / df
        if not os.path.exists(config.JSON_FILE):
            Data.create_new_json(temp_dutch_voc_list, temp_german_voc_list, temp_phonetics_list)

        # when there is a json file, then load the lists from the file and adjust them
        if os.path.exists(config.JSON_FILE):
            Data.load_data_json()
            Data.adjust_json_from_excel(temp_dutch_voc_list, temp_german_voc_list, temp_phonetics_list)

    def create_new_json(temp_dutch_voc_list: list, temp_german_voc_list: list, temp_phonetics_list: list) -> None:
        """Create a new json file with the vocabulary data."""
        print("No json data found. Creating new json data...")
        Data.dutch_voc_list = temp_dutch_voc_list
        Data.german_voc_list = temp_german_voc_list
        Data.phonetics_list = temp_phonetics_list
        Data.asked = [0] * len(temp_dutch_voc_list)
        Data.correct = [0] * len(temp_dutch_voc_list)
        Data.wrong = [0] * len(temp_dutch_voc_list)
        for i in range(len(temp_dutch_voc_list)):
            Data.points.append([])
            Data.d_g_points.append([])
            Data.g_d_points.append([])
        Data.last_asked = ["never"] * len(temp_dutch_voc_list)
        Data.current_date = [datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")]

        # combine dutch, german and phonetics list into a nested list, the data frame
        Data.data_frame = [Data.dutch_voc_list, Data.german_voc_list, Data.phonetics_list, Data.asked, Data.correct, Data.wrong, Data.points, Data.last_asked, Data.current_date]

    def adjust_json_from_excel(temp_dutch_voc_list: list, temp_german_voc_list: list, temp_phonetics_list: list) -> None:
        """
        Adjust the json data to the new vocabulary from the Excel file.
        The rows must not be changed in order (row 1 must always be reserved for the same vocabulary but we might slightly alter the dutch or german writing). There are three cases to consider:
        1.) german or dutch translation is altered but the amount of rows is the same: if yes change it in the json
        2.) more rows in xlsx than in json: add additional rows of xlsx to json and give them default values for asked, correct, wrong, points, last_asked
        3.) less rows in xlsx than in json: throw error and end program without saving data
        """
        # if same amount of rows in docx and json:
        if len(temp_dutch_voc_list) == len(Data.dutch_voc_list):
            for i in range(len(temp_dutch_voc_list)):
                # check for each row if dutch translation is altered
                if temp_dutch_voc_list[i] != Data.dutch_voc_list[i]:
                    print("New dutch description'", temp_dutch_voc_list[i], "' It will be added to the vocabulary list.")
                    Data.dutch_voc_list[i] = temp_dutch_voc_list[i]
                # check for each row if german translation is altered
                if temp_german_voc_list[i] != Data.german_voc_list[i]:
                    print("New german translation found for '", temp_dutch_voc_list[i], "' It will be added to the vocabulary list.")
                    Data.german_voc_list[i] = temp_german_voc_list[i]
                # check for each row if phonetics is altered
                if temp_phonetics_list[i] != Data.phonetics_list[i]:
                    print("New phonetics found for '", temp_dutch_voc_list[i], "' It will be added to the vocabulary list.")
                    Data.phonetics_list[i] = temp_phonetics_list[i]
        # elif more rows in docx than in json:
        elif len(temp_dutch_voc_list) > len(Data.dutch_voc_list):
            for i in range(len(Data.dutch_voc_list), len(temp_dutch_voc_list)):
                print("New word found: '", temp_dutch_voc_list[i], "' It will be added to the vocabulary list.")
                Data.dutch_voc_list.append(temp_dutch_voc_list[i])
                Data.german_voc_list.append(temp_german_voc_list[i])
                Data.phonetics_list.append(temp_phonetics_list[i])
                Data.asked.append(0)
                Data.correct.append(0)
                Data.wrong.append(0)
                Data.points.append([])
                Data.d_g_points.append([])
                Data.g_d_points.append([])
                Data.last_asked.append("never")
        # elif less rows in docx than in json
        elif len(temp_dutch_voc_list) < len(Data.dutch_voc_list):
            raise Exception("Error: The docx file contains less rows than the json file. Please add the missing rows to the docx file or delete the json file to create a new one.")


    def save_data_json() -> None:
        """Save the vocabulary data to a json file."""
        with open(config.JSON_FILE, 'w') as file:
            json.dump([ Data.dutch_voc_list, 
                        Data.german_voc_list, 
                        Data.phonetics_list,
                        Data.asked,
                        Data.correct,
                        Data.wrong,
                        Data.points,
                        Data.d_g_points,
                        Data.g_d_points,
                        Data.last_asked,
                        Data.current_date]
                       , file)

    def load_data_json() -> list:
        """Load the vocabulary data from a json file."""
        with open(config.JSON_FILE, 'r') as file:
            loaded_data_frame = json.load(file)
            Data.dutch_voc_list = loaded_data_frame[0]
            Data.german_voc_list = loaded_data_frame[1]
            Data.phonetics_list = loaded_data_frame[2]
            Data.asked = loaded_data_frame[3]
            Data.correct = loaded_data_frame[4]
            Data.wrong = loaded_data_frame[5]
            Data.points = loaded_data_frame[6]
            Data.d_g_points = loaded_data_frame[7]
            Data.g_d_points = loaded_data_frame[8]
            Data.last_asked = loaded_data_frame[9]
            Data.current_date = loaded_data_frame[10]

            # create empty lists for asked, correct, wrong, points, last_asked, if they don't exist yet
            nr_of_vocs = len(Data.dutch_voc_list)
            if len(Data.asked) == 0:
                Data.asked = [0] * nr_of_vocs
            if len(Data.correct) == 0:
                Data.correct = [0] * nr_of_vocs
            if len(Data.wrong) == 0:
                Data.wrong = [0] * nr_of_vocs
            if len(Data.points) == 0:
                for i in range(nr_of_vocs):
                    Data.points.append([])
            if len(Data.d_g_points) == 0:
                for i in range(nr_of_vocs):
                    Data.d_g_points.append([])
            if len(Data.g_d_points) == 0:
                for i in range(nr_of_vocs):
                    Data.g_d_points.append([])
            if len(Data.last_asked) == 0:
                for i in range(nr_of_vocs):
                    Data.last_asked.append("never")

            return loaded_data_frame

    def print_complete_voc_list() -> None:
        """Print the complete vocabulary list to the console."""
        for i in range(len(Data.dutch_voc_list)):
            print(Data.dutch_voc_list[i], " :: ", Data.german_voc_list[i])
            print("")

    def create_empty_xlsx(filename: str) -> None:
        """Create an empty Excel file with the correct structure."""
        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet.append(["DUTCH", "GERMAN", "NOTE"])
        workbook.save(filename)

    # -------------------------------------------------------------------------
    # SQLite persistence layer
    # -------------------------------------------------------------------------

    def init_db() -> None:
        """Create the SQLite database and vocabulary table if they do not exist."""
        os.makedirs(config.FILES_PATH, exist_ok=True)
        conn = sqlite3.connect(config.DB_FILE)
        conn.execute('''CREATE TABLE IF NOT EXISTS vocabulary (
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
        )''')
        conn.commit()
        conn.close()

    def migrate_to_sqlite() -> None:
        """Insert all current in-memory vocabulary into SQLite and archive old files."""
        Data.init_db()
        conn = sqlite3.connect(config.DB_FILE)
        for i in range(len(Data.dutch_voc_list)):
            conn.execute(
                'INSERT INTO vocabulary (dutch, german, note, asked, correct, wrong, points, d_g_points, g_d_points, last_asked) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (
                    Data.dutch_voc_list[i],
                    Data.german_voc_list[i],
                    Data.phonetics_list[i],
                    Data.asked[i],
                    Data.correct[i],
                    Data.wrong[i],
                    json.dumps(Data.points[i]),
                    json.dumps(Data.d_g_points[i]),
                    json.dumps(Data.g_d_points[i]),
                    Data.last_asked[i],
                )
            )
        conn.commit()
        conn.close()
        # Archive source files so data is not lost
        if os.path.exists(config.JSON_FILE):
            os.rename(config.JSON_FILE, config.JSON_FILE + '.backup')
        if os.path.exists(config.XLSX_FILE):
            os.rename(config.XLSX_FILE, config.XLSX_FILE + '.backup')
        print(f"Migration to SQLite complete: {len(Data.dutch_voc_list)} words written.")

    def load_data_sqlite() -> None:
        """Load all vocabulary rows from SQLite into the in-memory parallel lists."""
        conn = sqlite3.connect(config.DB_FILE)
        rows = conn.execute(
            'SELECT id, dutch, german, note, asked, correct, wrong, points, d_g_points, g_d_points, last_asked FROM vocabulary ORDER BY id'
        ).fetchall()
        conn.close()

        Data.id_list = []
        Data.dutch_voc_list = []
        Data.german_voc_list = []
        Data.phonetics_list = []
        Data.asked = []
        Data.correct = []
        Data.wrong = []
        Data.points = []
        Data.d_g_points = []
        Data.g_d_points = []
        Data.last_asked = []

        for row in rows:
            Data.id_list.append(row[0])
            Data.dutch_voc_list.append(row[1])
            Data.german_voc_list.append(row[2])
            Data.phonetics_list.append(row[3])
            Data.asked.append(row[4])
            Data.correct.append(row[5])
            Data.wrong.append(row[6])
            Data.points.append(json.loads(row[7]))
            Data.d_g_points.append(json.loads(row[8]))
            Data.g_d_points.append(json.loads(row[9]))
            Data.last_asked.append(row[10])

        Data.data_frame = [
            Data.dutch_voc_list, Data.german_voc_list, Data.phonetics_list,
            Data.asked, Data.correct, Data.wrong, Data.points,
            Data.last_asked, Data.current_date
        ]
        print(f"Loaded {len(Data.dutch_voc_list)} vocabulary words from SQLite.")

    def save_row_sqlite(vocab_index: int) -> None:
        """Persist the stats of a single vocabulary word to SQLite."""
        db_id = Data.id_list[vocab_index]
        conn = sqlite3.connect(config.DB_FILE)
        conn.execute(
            'UPDATE vocabulary SET asked=?, correct=?, wrong=?, points=?, d_g_points=?, g_d_points=?, last_asked=? WHERE id=?',
            (
                Data.asked[vocab_index],
                Data.correct[vocab_index],
                Data.wrong[vocab_index],
                json.dumps(Data.points[vocab_index]),
                json.dumps(Data.d_g_points[vocab_index]),
                json.dumps(Data.g_d_points[vocab_index]),
                Data.last_asked[vocab_index],
                db_id,
            )
        )
        conn.commit()
        conn.close()

    def add_vocabulary_to_db(dutch: str, german: str, note: str) -> int:
        """Insert a new word into SQLite and append it to the in-memory lists. Returns the new DB id."""
        conn = sqlite3.connect(config.DB_FILE)
        cursor = conn.execute(
            'INSERT INTO vocabulary (dutch, german, note) VALUES (?,?,?)',
            (dutch, german, note)
        )
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        Data.id_list.append(new_id)
        Data.dutch_voc_list.append(dutch)
        Data.german_voc_list.append(german)
        Data.phonetics_list.append(note)
        Data.asked.append(0)
        Data.correct.append(0)
        Data.wrong.append(0)
        Data.points.append([])
        Data.d_g_points.append([])
        Data.g_d_points.append([])
        Data.last_asked.append('never')
        return new_id

    def delete_vocabulary_from_db(db_id: int) -> None:
        """Delete a word from SQLite and remove it from all in-memory lists."""
        conn = sqlite3.connect(config.DB_FILE)
        conn.execute('DELETE FROM vocabulary WHERE id=?', (db_id,))
        conn.commit()
        conn.close()
        idx = Data.id_list.index(db_id)
        Data.id_list.pop(idx)
        Data.dutch_voc_list.pop(idx)
        Data.german_voc_list.pop(idx)
        Data.phonetics_list.pop(idx)
        Data.asked.pop(idx)
        Data.correct.pop(idx)
        Data.wrong.pop(idx)
        Data.points.pop(idx)
        Data.d_g_points.pop(idx)
        Data.g_d_points.pop(idx)
        Data.last_asked.pop(idx)

    def update_vocabulary_in_db(db_id: int, dutch: str, german: str, note: str) -> None:
        """Update the Dutch, German, and note fields for a word in SQLite and in memory."""
        conn = sqlite3.connect(config.DB_FILE)
        conn.execute(
            'UPDATE vocabulary SET dutch=?, german=?, note=? WHERE id=?',
            (dutch, german, note, db_id)
        )
        conn.commit()
        conn.close()
        idx = Data.id_list.index(db_id)
        Data.dutch_voc_list[idx] = dutch
        Data.german_voc_list[idx] = german
        Data.phonetics_list[idx] = note

class GUI:
    """A class to handle the user interface with pyqt"""
    STYLESHEET = """
        * {
            font-family: "Segoe UI", Arial, sans-serif;
        }
        QMainWindow, QDialog, QMessageBox {
            background-color: #F4F6FB;
        }
        QLabel {
            color: #1F2937;
            background-color: transparent;
        }
        QLabel#pageTitle {
            color: #111827;
            font-size: 30px;
            font-weight: 300;
        }
        QLabel#pageSubtitle {
            color: #6B7280;
            font-size: 15px;
        }
        QLabel#fieldLabel {
            color: #4B5563;
            font-size: 13px;
            font-weight: 600;
        }
        QLabel#hint {
            color: #6B7280;
            font-size: 13px;
        }
        QLabel#ratingValue {
            color: #4F46E5;
            font-size: 22px;
            font-weight: 600;
        }
        QLabel#card, QLabel#sentenceCard, QLabel#info {
            background-color: #FFFFFF;
            border: 1px solid #E3E8EF;
            border-radius: 14px;
            padding: 24px;
            color: #111827;
        }
        QLabel#card {
            font-size: 30px;
            font-weight: 300;
        }
        QLabel#sentenceCard {
            font-size: 21px;
            color: #374151;
        }
        QLabel#info {
            font-size: 20px;
            color: #4B5563;
        }
        QFrame#panel {
            background-color: #FFFFFF;
            border: 1px solid #E3E8EF;
            border-radius: 14px;
        }

        /* Buttons: primary by default, variants via the "variant" property */
        QPushButton {
            background-color: #4F46E5;
            color: #FFFFFF;
            border: none;
            border-radius: 10px;
            padding: 10px 22px;
            font-size: 15px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #4338CA;
        }
        QPushButton:pressed {
            background-color: #3730A3;
        }
        QPushButton:focus {
            outline: none;
        }
        QPushButton[variant="secondary"] {
            background-color: #FFFFFF;
            color: #374151;
            border: 1px solid #D1D5DB;
        }
        QPushButton[variant="secondary"]:hover {
            background-color: #F3F4F6;
            border-color: #9CA3AF;
        }
        QPushButton[variant="secondary"]:pressed {
            background-color: #E5E7EB;
        }
        QPushButton[variant="danger"] {
            background-color: #FFFFFF;
            color: #DC2626;
            border: 1px solid #FCA5A5;
        }
        QPushButton[variant="danger"]:hover {
            background-color: #FEF2F2;
            border-color: #DC2626;
        }
        QPushButton[variant="danger"]:pressed {
            background-color: #FEE2E2;
        }

        QSlider::groove:horizontal {
            height: 8px;
            background: #E5E7EB;
            border-radius: 4px;
        }
        QSlider::sub-page:horizontal {
            background: #6366F1;
            border-radius: 4px;
        }
        QSlider::handle:horizontal {
            background: #FFFFFF;
            border: 3px solid #4F46E5;
            width: 18px;
            height: 18px;
            margin: -8px 0;
            border-radius: 12px;
        }
        QSlider::handle:horizontal:hover {
            background: #EEF2FF;
        }

        QComboBox, QLineEdit {
            background-color: #FFFFFF;
            color: #1F2937;
            border: 1px solid #D1D5DB;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 15px;
            selection-background-color: #C7D2FE;
            selection-color: #1F2937;
        }
        QComboBox:hover, QLineEdit:hover {
            border-color: #9CA3AF;
        }
        QComboBox:focus, QLineEdit:focus {
            border: 1px solid #6366F1;
        }
        QComboBox::drop-down {
            border: none;
            width: 32px;
        }
        QComboBox::down-arrow {
            image: url("{CHEVRON_DOWN}");
            width: 12px;
            height: 8px;
            margin-right: 12px;
        }
        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            border: 1px solid #E3E8EF;
            selection-background-color: #EEF2FF;
            selection-color: #1F2937;
            outline: none;
            padding: 4px;
        }

        /* Tables (QTableView and QTableWidget) */
        QTableView {
            background-color: #FFFFFF;
            alternate-background-color: #F9FAFB;
            border: 1px solid #E3E8EF;
            border-radius: 12px;
            gridline-color: transparent;
            selection-background-color: #E0E7FF;
            selection-color: #111827;
            color: #1F2937;
            font-size: 14px;
            outline: none;
        }
        QTableView::item {
            padding: 0px 12px;
            border: none;
        }
        QTableView::item:hover {
            background-color: #F3F4F6;
        }
        QTableView::item:selected {
            background-color: #E0E7FF;
            color: #111827;
        }
        QHeaderView {
            background-color: transparent;
        }
        QHeaderView::section {
            background-color: #F9FAFB;
            color: #4B5563;
            font-weight: 600;
            font-size: 13px;
            border: none;
            border-bottom: 1px solid #E3E8EF;
            padding: 10px 12px;
        }
        QHeaderView::section:hover {
            background-color: #EEF2FF;
            color: #1F2937;
        }
        QTableCornerButton::section {
            background-color: #F9FAFB;
            border: none;
        }

        QScrollBar:vertical {
            background: transparent;
            width: 12px;
            margin: 4px 2px;
        }
        QScrollBar::handle:vertical {
            background: #CBD5E1;
            border-radius: 4px;
            min-height: 32px;
        }
        QScrollBar:horizontal {
            background: transparent;
            height: 12px;
            margin: 2px 4px;
        }
        QScrollBar::handle:horizontal {
            background: #CBD5E1;
            border-radius: 4px;
            min-width: 32px;
        }
        QScrollBar::handle:hover {
            background: #94A3B8;
        }
        QScrollBar::add-line, QScrollBar::sub-line,
        QScrollBar::add-page, QScrollBar::sub-page {
            background: none;
            border: none;
            width: 0px;
            height: 0px;
        }

        QToolTip {
            background-color: #111827;
            color: #F9FAFB;
            border: none;
            padding: 6px 8px;
            font-size: 13px;
        }
        QMessageBox QPushButton {
            min-width: 90px;
            min-height: 20px;
        }
    """

    def __init__(self) -> None:
        # initialize the pygame mixer for playing sound files
        mixer.init()

        self.app = QApplication([])
        # absolute path, because the working directory changes during runtime (os.chdir)
        chevron_path = os.path.join(config.MAIN_PATH, config.FILES_PATH, "chevron_down.svg").replace("\\", "/")
        self.app.setStyleSheet(GUI.STYLESHEET.replace("{CHEVRON_DOWN}", chevron_path))
        self.window = QMainWindow()
        self.start_main_menu()

    # LAYOUT HELPERS

    def _new_page(self, centered: bool = True) -> QVBoxLayout:
        """Replace the central widget with an empty page and return its layout."""
        central_widget = QWidget()
        self.window.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(14)
        if centered:
            layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        else:
            layout.setContentsMargins(32, 28, 32, 28)
        return layout

    @staticmethod
    def _title_block(title: str, subtitle: str = "", centered: bool = True) -> QVBoxLayout:
        """Create a page title with an optional subtitle underneath."""
        block = QVBoxLayout()
        block.setSpacing(4)
        alignment = Qt.AlignmentFlag.AlignCenter if centered else Qt.AlignmentFlag.AlignLeft
        title_label = QLabel(title)
        title_label.setObjectName("pageTitle")
        title_label.setAlignment(alignment)
        block.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("pageSubtitle")
            subtitle_label.setAlignment(alignment)
            block.addWidget(subtitle_label)
        return block

    @staticmethod
    def _button(text: str, variant: str = "", width: int | None = None, height: int = 52) -> QPushButton:
        """Create a button; variant is "" (primary), "secondary" or "danger"."""
        button = QPushButton(text)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        if variant:
            button.setProperty("variant", variant)
        if width:
            button.setFixedSize(width, height)
        else:
            button.setFixedHeight(height)
        return button

    @staticmethod
    def _set_variant(button: QPushButton, variant: str) -> None:
        """Change the variant of an already visible button and re-apply the stylesheet."""
        button.setProperty("variant", variant)
        button.style().unpolish(button)
        button.style().polish(button)

    @staticmethod
    def _hint(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("hint")
        return label

    def _rating_widget(self, width: int) -> QWidget:
        """Create the slider to rate how well a word was known; the slider is stored in self.slider."""
        container = QWidget()
        container.setFixedWidth(width)
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 6, 0, 6)
        grid.setVerticalSpacing(4)

        value_label = QLabel()
        value_label.setObjectName("ratingValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setSingleStep(1)
        self.slider.setPageStep(10)
        self.slider.setFixedHeight(30)
        self.slider.setCursor(Qt.CursorShape.PointingHandCursor)

        def update_value(value: int) -> None:
            value_label.setText(str(value))
            value_label.setStyleSheet(f"color: {score_color(value)};")

        self.slider.valueChanged.connect(update_value)
        self.slider.setSliderPosition(50)
        update_value(50)

        high_label = GUI._hint("Knew it perfectly")
        high_label.setAlignment(Qt.AlignmentFlag.AlignRight)

        grid.addWidget(GUI._hint("How well did you know it?"), 0, 0)
        grid.addWidget(value_label, 0, 1)
        grid.addWidget(self.slider, 1, 0, 1, 2)
        grid.addWidget(GUI._hint("Not at all"), 2, 0)
        grid.addWidget(high_label, 2, 1)
        container.setFixedHeight(container.sizeHint().height())
        return container

    @staticmethod
    def _style_table(table: QTableView) -> None:
        """Apply the common look of all tables: no grid, zebra rows, comfortable row height."""
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(40)
        table.horizontalHeader().setHighlightSections(False)
        table.horizontalHeader().setMinimumSectionSize(70)
        table.horizontalHeader().setFixedHeight(42)

    # SCREENS

    def start_main_menu(self) -> None:
        """Set up the main menu as part of the GUI."""
        layout = self._new_page()

        layout.addLayout(GUI._title_block('Vocabulary Trainer', 'Dutch ↔ German'))
        layout.addSpacing(30)

        button_width = 300

        self.start_training_button = GUI._button('Start Training', width=button_width)
        self.explore_statistics_button = GUI._button('Explore Statistics', width=button_width)
        self.manage_vocabulary_button = GUI._button('Manage Vocabulary', width=button_width)
        self.exit_button = GUI._button('Exit', "secondary", width=button_width)

        layout.addWidget(self.start_training_button)
        layout.addWidget(self.explore_statistics_button)
        layout.addWidget(self.manage_vocabulary_button)
        layout.addSpacing(12)
        layout.addWidget(self.exit_button)

        self.start_training_button.clicked.connect(self.select_training_type)
        self.explore_statistics_button.clicked.connect(self.explore_statistics)
        self.manage_vocabulary_button.clicked.connect(self.manage_vocabulary)
        self.exit_button.clicked.connect(QApplication.instance().quit)

        self.window.setWindowTitle('Vocabulary Trainer')
        self.window.showMaximized()

    def select_training_type(self) -> None:
        """Set up the training type selection screen as part of the GUI."""
        layout = self._new_page()

        layout.addLayout(GUI._title_block('Choose a Training Mode', 'Pick the direction you want to practise'))
        layout.addSpacing(30)

        button_width = 320

        button_dutch_german = GUI._button('Dutch → German', width=button_width)
        button_german_dutch = GUI._button('German → Dutch', width=button_width)
        button_random = GUI._button('Random Direction', width=button_width)
        button_advanced_mode = GUI._button('Advanced Mode (AI)', width=button_width)
        button_back = GUI._button('Back', "secondary", width=button_width)

        layout.addWidget(button_dutch_german)
        layout.addWidget(button_german_dutch)
        layout.addWidget(button_random)
        layout.addWidget(button_advanced_mode)
        layout.addSpacing(12)
        layout.addWidget(button_back)

        # Connect button clicks to their respective functions
        button_dutch_german.clicked.connect(self.start_dutch_german)
        button_german_dutch.clicked.connect(self.start_german_dutch)
        button_random.clicked.connect(self.start_random)
        button_advanced_mode.clicked.connect(self.start_advanced_mode)
        button_back.clicked.connect(self.start_main_menu)

    def end_training(self) -> None:
        """End the training and return to the main menu when the user clicks the 'End Training' button."""
        GUI.start_main_menu(self)

    def start_dutch_german(self) -> None:
        """Set up the training screen for Dutch -> German translations."""
        logic.modus = "DG" # change the modus to DG
        slider_added = False # boolean to check if a slider was already added

        def show_translation() -> None:
            """Show the translation of the Dutch word and add a slider to evaluate how well the translation was known."""
            nonlocal label_text
            nonlocal slider_added
            if label_text == Logic.short_lines(dutch_word)+"\n"+phonetics:
                label_text = Logic.short_lines(correct_translation)
            else:
                label_text = Logic.short_lines(dutch_word)+"\n"+phonetics
            label.setText(label_text)

            if not slider_added:
                # replace "End Training" with the rating slider and "Next Vocabulary"
                layout.removeWidget(button_end_training)
                button_end_training.hide()
                button_end_training.deleteLater()
                button_translate.setText('Flip Card')
                GUI._set_variant(button_translate, "secondary")
                layout.addWidget(self._rating_widget(card_width))
                layout.addWidget(button_next_vok)
                slider_added = True

        def next_vocab() -> None:
            """Save the statistics and continue with the next vocabulary."""
            print(vocab_nr)
            # add +1 to asked
            Data.asked[vocab_nr] += 1
            # add date to last_asked
            Data.last_asked[vocab_nr] = Data.current_date[-1]
            # add current points to list of all points
            Data.points[vocab_nr].append(self.slider.value())
            # add current points to list of German->Dutch translations
            Data.d_g_points[vocab_nr].append(self.slider.value())
            # add +1 to correct or wrong
            if self.slider.value() > 60:
                Data.correct[vocab_nr] += 1
            elif self.slider.value() < 40:
                Data.wrong[vocab_nr] += 1

            # save statistics
            Data.save_row_sqlite(vocab_nr)
            # ask for a new vocab
            GUI.start_dutch_german(self)

        # SET UP THE LAYOUT

        layout = self._new_page()
        card_width = 560

        dutch_word, correct_translation, phonetics, vocab_nr = Logic.ask_question()

        label_text = Logic.short_lines(dutch_word)+"\n"+phonetics
        label = QLabel(label_text, alignment=Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("card")
        label.setFixedSize(card_width, 300)

        button_translate = GUI._button('Show Translation', width=card_width)
        button_end_training = GUI._button('End Training', "secondary", width=card_width)
        button_next_vok = GUI._button('Next Vocabulary', width=card_width)

        layout.addWidget(GUI._hint('Dutch → German'), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label)
        layout.addWidget(button_translate)
        layout.addWidget(button_end_training)

        button_translate.clicked.connect(show_translation)
        button_end_training.clicked.connect(self.end_training)
        button_next_vok.clicked.connect(next_vocab)

    def start_german_dutch(self) -> None:
        """Set up the training screen for German -> Dutch translations."""
        logic.modus = "GD" # change the modus to GD
        slider_added = False # boolean to check if a slider was already added

        # show translation of the word; make slider visible
        def show_translation():
            nonlocal label_text
            nonlocal slider_added
            if label_text == Logic.short_lines(dutch_word)+"\n"+phonetics:
                label_text = Logic.short_lines(german_word)
            else:
                label_text = Logic.short_lines(dutch_word)+"\n"+phonetics
            label.setText(label_text)

            if not slider_added:
                # replace "End Training" with the rating slider and "Next Vocabulary"
                layout.removeWidget(button_end_training)
                button_end_training.hide()
                button_end_training.deleteLater()
                button_translate.setText('Flip Card')
                GUI._set_variant(button_translate, "secondary")
                layout.addWidget(self._rating_widget(card_width))
                layout.addWidget(button_next_vok)
                slider_added = True

        # save the statistics and continue with next word
        def next_vocab():
            print(vocab_nr)
            # add +1 to asked
            Data.asked[vocab_nr] += 1
            # add date to last_asked
            Data.last_asked[vocab_nr] = Data.current_date[-1]
            # add current points to list of all points
            Data.points[vocab_nr].append(self.slider.value())
            # add current points to list of German->Dutch translations
            Data.g_d_points[vocab_nr].append(self.slider.value())
            # add +1 to correct or wrong
            if self.slider.value() > 60:
                Data.correct[vocab_nr] += 1
            elif self.slider.value() < 40:
                Data.wrong[vocab_nr] += 1

            # save statistics
            Data.save_row_sqlite(vocab_nr)
            # ask for a new vocab
            GUI.start_german_dutch(self)

        # SET UP THE LAYOUT

        layout = self._new_page()
        card_width = 560

        # Create a QLabel with vocabulary to ask
        dutch_word, correct_translation, phonetics, vocab_nr = Logic.ask_question()
        german_word = correct_translation

        # ToDo: if phenetics is empty, don't show it
        label_text = Logic.short_lines(german_word)
        label = QLabel(label_text, alignment=Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("card")
        label.setFixedSize(card_width, 300)

        button_translate = GUI._button('Show Translation', width=card_width)
        button_end_training = GUI._button('End Training', "secondary", width=card_width)
        button_next_vok = GUI._button('Next Vocabulary', width=card_width)

        layout.addWidget(GUI._hint('German → Dutch'), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label)
        layout.addWidget(button_translate)
        layout.addWidget(button_end_training)

        # Connect button clicks to their respective functions
        button_translate.clicked.connect(show_translation)
        button_end_training.clicked.connect(self.end_training)
        button_next_vok.clicked.connect(next_vocab)

    def start_random(self) -> None:
        """Set up the training screen for random translations."""
        logic.modus = "RA" # change the modus to RA
        slider_added = False # boolean to check if a slider was already added
        direction = ""

        def show_translation() -> None:
            """Show the translation of the Dutch word and add a slider to evaluate how well the translation was known."""
            nonlocal label_text
            nonlocal slider_added
            nonlocal direction
            if label_text == Logic.short_lines(dutch_word)+"\n"+phonetics:
                label_text = Logic.short_lines(correct_translation)
                direction = "Dutch -> German"
            else:
                label_text = Logic.short_lines(dutch_word)+"\n"+phonetics
                direction = "German -> Dutch"
            label.setText(label_text)

            if not slider_added:
                # replace "End Training" with the rating slider and "Next Vocabulary"
                layout.removeWidget(button_end_training)
                button_end_training.hide()
                button_end_training.deleteLater()
                button_translate.setText('Flip Card')
                GUI._set_variant(button_translate, "secondary")
                layout.addWidget(self._rating_widget(card_width))
                layout.addWidget(button_next_vok)
                slider_added = True

        def next_vocab() -> None:
            """Save the statistics and continue with the next vocabulary."""
            global vocab_nr
            print(vocab_nr)
            # add +1 to asked
            Data.asked[vocab_nr] += 1
            # add date to last_asked
            Data.last_asked[vocab_nr] = Data.current_date[-1]
            # add current points to list of all points
            Data.points[vocab_nr].append(self.slider.value())
            # add current points to list of German->Dutch translations or Dutch->German translations
            if direction == "Dutch -> German":
                Data.d_g_points[vocab_nr].append(self.slider.value())
            elif direction == "German -> Dutch":
                Data.g_d_points[vocab_nr].append(self.slider.value())
            # add +1 to correct or wrong
            if self.slider.value() > 60:
                Data.correct[vocab_nr] += 1
            elif self.slider.value() < 40:
                Data.wrong[vocab_nr] += 1

            # save statistics
            Data.save_row_sqlite(vocab_nr)
            # ask for a new vocab
            GUI.start_random(self)

        # SET UP THE LAYOUT

        layout = self._new_page()
        card_width = 560

        # Create a QLabel with vocabulary to ask
        dutch_word, correct_translation, phonetics, vocab_nr = Logic.ask_question()

        # ToDo: if phenetics is empty, don't show it
        if random.randint(0,1) == 0:
            label_text = Logic.short_lines(dutch_word)+"\n"+phonetics
            mode_text = 'Dutch → German'
        else:
            label_text = Logic.short_lines(correct_translation)
            mode_text = 'German → Dutch'
        label = QLabel(label_text, alignment=Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("card")
        label.setFixedSize(card_width, 300)

        button_translate = GUI._button('Show Translation', width=card_width)
        button_end_training = GUI._button('End Training', "secondary", width=card_width)
        button_next_vok = GUI._button('Next Vocabulary', width=card_width)

        layout.addWidget(GUI._hint(f'Random · {mode_text}'), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label)
        layout.addWidget(button_translate)
        layout.addWidget(button_end_training)

        # Connect button clicks to their respective functions
        button_translate.clicked.connect(show_translation)
        button_end_training.clicked.connect(self.end_training)
        button_next_vok.clicked.connect(next_vocab)

    def start_ai_sentences(self) -> None:
        """Set up the training screen for AI generated sentences."""
        logic.modus = "AI" # change the modus to AI
        slider_added = False # boolean to check if a slider was already added

        def show_translation() -> None:
            """Show the translation of the Dutch word and add a slider to evaluate how well the translation was known."""
            nonlocal label_text
            nonlocal label_text_ai
            nonlocal slider_added

            # change the label for the vocabulary (first QLabel)
            if label_text == Logic.short_lines(dutch_word, pixel=800)+"\n"+phonetics:
                label_text = Logic.short_lines(correct_translation, pixel=800)
            else:
                label_text = Logic.short_lines(dutch_word, pixel=800)+"\n"+phonetics
            label.setText(label_text)

            # change the label for the ai sentence (second QLabel)
            if label_text_ai == Logic.short_lines(ai_sentence, pixel=800):
                label_text_ai = Logic.short_lines(ai_sentence_translation, pixel=800)
            else:
                label_text_ai = Logic.short_lines(ai_sentence, pixel=800)
            label_ai_sentence.setText(label_text_ai)

            if not slider_added:
                # replace "End Training" with the rating slider and "Next Vocabulary"
                layout.removeWidget(button_end_training)
                button_end_training.hide()
                button_end_training.deleteLater()
                button_translate.setText('Flip Cards')
                GUI._set_variant(button_translate, "secondary")
                layout.addWidget(self._rating_widget(card_width))
                layout.addWidget(button_next_vok)
                slider_added = True

        def next_vocab() -> None:
            """Save the statistics and continue with the next vocabulary."""
            print(vocab_nr)
            # add +1 to asked
            Data.asked[vocab_nr] += 1
            # add date to last_asked
            Data.last_asked[vocab_nr] = Data.current_date[-1]
            # add current points to list of all points
            Data.points[vocab_nr].append(self.slider.value())
            # add current points to list of German->Dutch translations
            Data.d_g_points[vocab_nr].append(self.slider.value())
            # add +1 to correct or wrong
            if self.slider.value() > 60:
                Data.correct[vocab_nr] += 1
            elif self.slider.value() < 40:
                Data.wrong[vocab_nr] += 1

            # save statistics
            Data.save_row_sqlite(vocab_nr)
            # ask for a new vocab
            GUI.start_ai_sentences(self)

        # SET UP THE LAYOUT

        layout = self._new_page()
        card_width = 800

        # Create a QLabel with vocabulary to ask
        dutch_word, correct_translation, phonetics, vocab_nr = Logic.ask_question()

        label_text = Logic.short_lines(dutch_word)+"\n"+phonetics
        label = QLabel(label_text, alignment=Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("card")
        label.setFixedSize(card_width, 180)

        # generate data with AI
        ai_sentence = AiApi.generate_AI_sentence(dutch_word, aiapi.OpenAiClient)
        ai_sentence_translation = AiApi.generate_AI_translation(ai_sentence, aiapi.OpenAiClient)
        logic.sound_created = False

        # Create second Qlabel, which will show the AI sentence
        label_text_ai = Logic.short_lines(ai_sentence, pixel=800)
        label_ai_sentence = QLabel(label_text_ai, alignment=Qt.AlignmentFlag.AlignCenter)
        label_ai_sentence.setObjectName("sentenceCard")
        label_ai_sentence.setFixedSize(card_width, 260)

        button_translate = GUI._button('Show Translation', width=card_width)
        button_play_sound = GUI._button('▶  Play Sound', "secondary", width=card_width)
        button_end_training = GUI._button('End Training', "secondary", width=card_width)
        button_next_vok = GUI._button('Next Vocabulary', width=card_width)

        layout.addWidget(GUI._hint('AI Sentences · Dutch → German'), alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label)
        layout.addWidget(label_ai_sentence)
        layout.addWidget(button_translate)
        layout.addWidget(button_play_sound)
        layout.addWidget(button_end_training)

        # Connect button clicks to their respective functions
        button_translate.clicked.connect(show_translation)
        button_end_training.clicked.connect(self.end_training)
        button_next_vok.clicked.connect(next_vocab)
        button_play_sound.clicked.connect(lambda: AiApi.text_to_speech(ai_sentence, aiapi.OpenAiClient, logic.voice_model))

    def start_advanced_mode(self) -> None:
        """Set up the advanced mode screen with dropdowns for voice model, language direction, and sentence style."""
        logic.modus = "SE" # change the modus to settings
        # set all dropdowns to the first option in the logic_handler
        logic.voice_model = "alloy"
        logic.language_direction_ai = "DG"
        logic.sentence_style_ai = "normal"

        # SET UP THE LAYOUT

        layout = self._new_page()
        width = 420

        layout.addLayout(GUI._title_block('Advanced Mode', 'AI-generated example sentences with audio'))
        layout.addSpacing(24)

        def add_field(label_text: str, items: list) -> QComboBox:
            field_label = QLabel(label_text)
            field_label.setObjectName("fieldLabel")
            dropdown = QComboBox(self.window)
            dropdown.addItems(items)
            dropdown.setFixedSize(width, 46)
            dropdown.setCursor(Qt.CursorShape.PointingHandCursor)
            layout.addWidget(field_label)
            layout.addWidget(dropdown)
            layout.addSpacing(6)
            return dropdown

        # the item order must match the index handling in the on_*_change methods
        self.voice_model_dropdown = add_field("Voice", ["Alloy", "Echo", "Fable", "Nova", "Onyx", "Shimmer"])
        self.language_dropdown = add_field("Direction", ["Dutch → German", "German → Dutch"])
        self.sentence_style_dropdown = add_field("Sentence style", ["Normal", "Scientific", "Scary", "Offensive"])

        layout.addSpacing(18)
        button_start_advanced_training = GUI._button('Start Training', width=width)
        button_back = GUI._button('Back', "secondary", width=width)
        layout.addWidget(button_start_advanced_training)
        layout.addWidget(button_back)

        # Connect the signals to the slots
        self.voice_model_dropdown.currentIndexChanged.connect(self.on_voice_model_change)
        self.language_dropdown.currentIndexChanged.connect(self.on_language_change)
        self.sentence_style_dropdown.currentIndexChanged.connect(self.on_sentence_style_change)
        button_start_advanced_training.clicked.connect(self.start_ai_sentences)
        button_back.clicked.connect(self.select_training_type)

    def on_voice_model_change(self, index) -> None:
        """Change the voice model based on the selected index in the dropdown."""
        # set the voice model in the logic_handler
        logic.voice_model = self.voice_model_dropdown.itemText(index)
        if index == 0:
            logic.voice_model = "alloy"
            gui.play_sound("example_alloy.mp3")
        elif index == 1:
            logic.voice_model = "echo"
            gui.play_sound("example_echo.mp3")
        elif index == 2:
            logic.voice_model = "fable"
            gui.play_sound("example_fable.mp3")
        elif index == 3:
            logic.voice_model = "nova"
            gui.play_sound("example_nova.mp3")
        elif index == 4:
            logic.voice_model = "onyx"
            gui.play_sound("example_onyx.mp3")
        elif index == 5:
            logic.voice_model = "shimmer"
            gui.play_sound("example_shimmer.mp3")

    def on_language_change(self, index: int) -> None:
        """Change the language direction based on the selected index in the dropdown."""
        if index == 0:
            logic.language_direction_ai = "DG"
        elif index == 1:
            logic.language_direction_ai = "GD"

    def on_sentence_style_change(self, index: int) -> None:
        """Change the sentence style based on the selected index in the dropdown."""
        if index == 0:
            logic.sentence_style_ai = "creative"
        elif index == 1:
            logic.sentence_style_ai = "complex scientific"
        elif index == 2:
            logic.sentence_style_ai = "scary and dark"
        elif index == 3:
            logic.sentence_style_ai = "offensive"

    def explore_statistics(self) -> None:
        """Set up the statistics screen as part of the GUI."""
        layout = self._new_page(centered=False)

        # header: title on the left, search and back button on the right
        table_data = Logic.create_statistics_data()
        header = QHBoxLayout()
        header.addLayout(GUI._title_block('Statistics', f'{len(table_data)} words · click a column header to sort', centered=False))
        header.addStretch()
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search words…")
        search_input.setClearButtonEnabled(True)
        search_input.setFixedSize(300, 42)
        button_back_to_main_menu = GUI._button('Main Menu', "secondary", height=42)
        header.addWidget(search_input, alignment=Qt.AlignmentFlag.AlignBottom)
        header.addSpacing(8)
        header.addWidget(button_back_to_main_menu, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header)
        layout.addSpacing(6)

        # Create a pyqt table with that data; the proxy handles sorting and searching
        table = QTableView()
        model = Table(
            table_data,
            text_columns=('Dutch', 'German', 'Note'),
            score_columns=('Avg', 'Avg Last 10', 'Avg NL→DE', 'Avg DE→NL'),
            date_columns=('Last Asked',),
        )
        model.setParent(table)
        proxy = QSortFilterProxyModel(table)
        proxy.setSourceModel(model)
        proxy.setSortRole(Table.SORT_ROLE)
        proxy.setFilterKeyColumn(-1)
        proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        table.setModel(proxy)
        GUI._style_table(table)

        # word columns start wide enough for their content (capped, still resizable),
        # the note takes the remaining space, numeric columns fit their content
        header_view = table.horizontalHeader()
        for column in range(model.columnCount()):
            column_name = table_data.columns[column]
            if column_name in ('Dutch', 'German'):
                header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.Interactive)
                table.resizeColumnToContents(column)
                table.setColumnWidth(column, min(table.columnWidth(column) + 16, 320))
            elif column_name == 'Note':
                header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
            else:
                header_view.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)

        table.setSortingEnabled(True)
        table.sortByColumn(0, Qt.SortOrder.AscendingOrder)
        layout.addWidget(table)

        search_input.textChanged.connect(proxy.setFilterFixedString)
        button_back_to_main_menu.clicked.connect(self.start_main_menu)

    def refresh_vocabulary(self) -> None:
        """Refresh the vocabulary by loading the data from the xlsx file."""
        layout = self._new_page()

        # show message that the vocabulary is being refreshed
        info_label = QLabel("Refreshing vocabulary…", alignment=Qt.AlignmentFlag.AlignCenter)
        info_label.setObjectName("info")
        info_label.setFixedSize(500, 220)
        layout.addWidget(info_label)

        # force the program to show the label (otherwise it will only show it after the vocabulary is refreshed)
        QCoreApplication.processEvents()

        # # actually refresh the data
        try:
            Data.load_and_check_xlsx(config.XLSX_FILE)
            Data.save_data_json()
        except Exception as e:
            print(f"\n\nError while loading vocabulary: \n{e}")

        # go back to main menu
        GUI.start_main_menu(self)

    def no_more_vocs(self) -> None:
        """Set up the layout for the 'no more vocs' message."""
        layout = self._new_page()

        info_label = QLabel("Congrats! All vocabularies were trained once!\nThe program will end now.", alignment=Qt.AlignmentFlag.AlignCenter)
        info_label.setObjectName("info")
        info_label.setFixedSize(640, 300)
        layout.addWidget(info_label)

        # force the program to show the label before it ends
        QCoreApplication.processEvents()

    def play_sound(self, file_name: str) -> None:
        """Play a sound file from the files folder."""
        os.chdir(config.FILES_PATH)
        # make a copy of the file so that it can be overwritten
        mixer.music.load(file_name)  # Load the sound file
        mixer.music.play()  # Play the sound file
        # wait until the sound is finished playing
        while mixer.music.get_busy():
            pass
        # load a dummy file so that the "generated_audio.mp3" can be overwritten and be used again
        mixer.music.load("audio_dummy.wav")
        os.chdir(config.MAIN_PATH)

    def manage_vocabulary(self) -> None:
        """Screen for adding, editing, and deleting vocabulary words."""
        layout = self._new_page(centered=False)

        # Header: title on the left, search and back button on the right
        header = QHBoxLayout()
        title_block = GUI._title_block('Manage Vocabulary', centered=False)
        count_label = QLabel()
        count_label.setObjectName("pageSubtitle")
        title_block.addWidget(count_label)
        header.addLayout(title_block)
        header.addStretch()
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search words…")
        search_input.setClearButtonEnabled(True)
        search_input.setFixedSize(300, 42)
        btn_back = GUI._button("Main Menu", "secondary", height=42)
        header.addWidget(search_input, alignment=Qt.AlignmentFlag.AlignBottom)
        header.addSpacing(8)
        header.addWidget(btn_back, alignment=Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(header)
        layout.addSpacing(6)

        # Table
        vocab_table = QTableWidget()
        vocab_table.setColumnCount(3)
        vocab_table.setHorizontalHeaderLabels(['Dutch', 'German', 'Note'])
        vocab_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        GUI._style_table(vocab_table)
        for column in range(3):
            vocab_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        for column in range(3):
            vocab_table.horizontalHeaderItem(column).setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(vocab_table)

        self._selected_vocab_db_id = None

        def apply_filter() -> None:
            text = search_input.text().strip().lower()
            for row in range(vocab_table.rowCount()):
                matches = not text or any(text in vocab_table.item(row, c).text().lower() for c in range(3))
                vocab_table.setRowHidden(row, not matches)

        def refresh_table() -> None:
            vocab_table.setRowCount(len(Data.dutch_voc_list))
            for i in range(len(Data.dutch_voc_list)):
                for column, value in enumerate((Data.dutch_voc_list[i], Data.german_voc_list[i], Data.phonetics_list[i])):
                    item = QTableWidgetItem(str(value))
                    item.setToolTip(str(value))
                    if column == 0:
                        font = item.font()
                        font.setWeight(QFont.Weight.DemiBold)
                        item.setFont(font)
                    vocab_table.setItem(i, column, item)
            vocab_table.clearSelection()
            self._selected_vocab_db_id = None
            dutch_input.clear()
            german_input.clear()
            note_input.clear()
            count_label.setText(f"{len(Data.dutch_voc_list)} words · select a row to edit it")
            apply_filter()

        # Edit panel: inputs with labels above them, buttons below
        panel = QFrame()
        panel.setObjectName("panel")
        panel_layout = QGridLayout(panel)
        panel_layout.setContentsMargins(20, 16, 20, 20)
        panel_layout.setHorizontalSpacing(12)
        panel_layout.setVerticalSpacing(6)

        def add_input(column: int, label_text: str, placeholder: str, stretch: int) -> QLineEdit:
            field_label = QLabel(label_text)
            field_label.setObjectName("fieldLabel")
            field_input = QLineEdit()
            field_input.setPlaceholderText(placeholder)
            field_input.setFixedHeight(42)
            panel_layout.addWidget(field_label, 0, column)
            panel_layout.addWidget(field_input, 1, column)
            panel_layout.setColumnStretch(column, stretch)
            return field_input

        dutch_input = add_input(0, "Dutch", "Dutch word…", 2)
        german_input = add_input(1, "German", "German translation…", 2)
        note_input = add_input(2, "Note", "Phonetics / note…", 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_add = GUI._button("Add Word", height=42)
        btn_update = GUI._button("Update Selected", "secondary", height=42)
        btn_delete = GUI._button("Delete Selected", "danger", height=42)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_update)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_delete)
        panel_layout.addLayout(btn_layout, 2, 0, 1, 3)
        panel_layout.setRowMinimumHeight(2, 58)
        layout.addWidget(panel)

        def on_row_selected() -> None:
            if not vocab_table.selectedItems():
                self._selected_vocab_db_id = None
                return
            row = vocab_table.currentRow()
            self._selected_vocab_db_id = Data.id_list[row]
            dutch_input.setText(str(Data.dutch_voc_list[row]))
            german_input.setText(str(Data.german_voc_list[row]))
            note_input.setText(str(Data.phonetics_list[row]))

        def on_add() -> None:
            dutch = dutch_input.text().strip()
            german = german_input.text().strip()
            note = note_input.text().strip()
            if not dutch or not german:
                msg = QMessageBox(self.window)
                msg.setWindowTitle("Missing Data")
                msg.setText("Dutch and German fields are required.")
                msg.exec()
                return
            Data.add_vocabulary_to_db(dutch, german, note)
            refresh_table()

        def on_update() -> None:
            if self._selected_vocab_db_id is None:
                msg = QMessageBox(self.window)
                msg.setWindowTitle("No Selection")
                msg.setText("Please select a word to update.")
                msg.exec()
                return
            dutch = dutch_input.text().strip()
            german = german_input.text().strip()
            note = note_input.text().strip()
            if not dutch or not german:
                msg = QMessageBox(self.window)
                msg.setWindowTitle("Missing Data")
                msg.setText("Dutch and German fields are required.")
                msg.exec()
                return
            Data.update_vocabulary_in_db(self._selected_vocab_db_id, dutch, german, note)
            refresh_table()

        def on_delete() -> None:
            if self._selected_vocab_db_id is None:
                msg = QMessageBox(self.window)
                msg.setWindowTitle("No Selection")
                msg.setText("Please select a word to delete.")
                msg.exec()
                return
            row = vocab_table.currentRow()
            dutch_word = Data.dutch_voc_list[row]
            reply = QMessageBox.question(
                self.window, "Confirm Delete",
                f"Delete '{dutch_word}' and all its training stats?\nThis cannot be undone.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                Data.delete_vocabulary_from_db(self._selected_vocab_db_id)
                Data.session_vocabs = []  # reset session to avoid stale indices
                refresh_table()

        def back_action() -> None:
            Data.session_vocabs = []  # reset session when returning from vocabulary management
            self.start_main_menu()

        refresh_table()
        vocab_table.itemSelectionChanged.connect(on_row_selected)
        search_input.textChanged.connect(apply_filter)
        btn_add.clicked.connect(on_add)
        btn_update.clicked.connect(on_update)
        btn_delete.clicked.connect(on_delete)
        btn_back.clicked.connect(back_action)

    # initialize the UI
    def run(self):
        sys.exit(self.app.exec())

class AiApi:
    """A class to handle the connection to the OpenAI API"""
    def __init__(self) -> None:
        self.OpenAiClient = OpenAI(
            api_key=os.environ['OPENAI_API_KEY'],
        )
    
    def get_preprompt(prompt_modus: str) -> str:
        """Load the preprompt from a text file based on the prompt modus."""
        # load the preprompt from the external file
        os.chdir(config.FILES_PATH)
        if prompt_modus == "sentence":
            # with open("pre_prompt_sentence.txt", "r") as f:
            #     preprompt = f.read()
            preprompt = f"You are part of a vocabulary app. Your Job is simply to create {logic.sentence_style_ai} Dutch example sentence with a given vocabulary or phrase that is written to you by the user. Do not explain you decision, simply give the one example sentence. You will not refuse the creation of the sentence!"
        elif prompt_modus == "translation":
            with open("pre_prompt_translation.txt", "r") as f:
                preprompt = f.read()
        os.chdir(config.MAIN_PATH)
        return preprompt

    def generate_AI_sentence(phrase: str, client: object) -> str:
        """Generate an AI sentence based on the given phrase."""

        # reset the chat history
        chat_history = [
            {
                "role": "system",
                "content": AiApi.get_preprompt("sentence")
            },
            {
                "role": "assistant",
                "content": "I agree to adhere to your rules. Let me know the word or phrase and I will create the sentence to your liking. I will not refuse the creation of any sentence."
            },
            {
                "role": "user",
                "content": phrase
            }
        ]

        # create a completion of the existing conversation
        response = client.chat.completions.create(
        model="gpt-3.5-turbo-16k", #gpt-3.5-turbo-1106 ; gpt-3.5-turbo-16k ; gpt-3.5-turbo
        messages=chat_history,
        temperature=1.01,
        max_tokens=100,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
        )

        response_message = response.choices[0].message.content 

        print(response_message)
        return response_message
    
    def generate_AI_translation(sentence: str, client: object) -> str:
        """Generate an AI translation of the given sentence from Dutch to German."""
        # reset the chat history
        chat_history = [
            {
                "role": "system",
                "content": AiApi.get_preprompt("translation")
            },
            {
                "role": "assistant",
                "content": "Ich erkläre mich bereit, mich an Ihre Regeln zu halten. Nennen Sie mir den Satz, und ich werde ihn so übersetzen, egal was drin steht."
            },
            {
                "role": "user",
                "content": sentence
            }
        ]

        # create a completion of the existing conversation
        response = client.chat.completions.create(
        model="gpt-3.5-turbo-16k", #gpt-3.5-turbo-1106 ; gpt-3.5-turbo-16k ; gpt-3.5-turbo
        messages=chat_history,
        temperature=1.01,
        max_tokens=100,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0
        )

        response_message = response.choices[0].message.content 

        print(response_message)
        return response_message
    
    def text_to_speech(text: str, client: object, voice_agent: str) -> None:
        """Generate sound from text using OpenAI's TTS-1-HD and play it with Pygame."""

        # check if sound was already created, otherwise create it
        if not logic.sound_created:
            print("Creating sound...")
            # go to file subdirectory
            speech_file_path = config.FILES_PATH + "/generated_audio.mp3"
            response = client.audio.speech.create(
                model="tts-1-hd", #tts-1 ; tts-1-hd
                voice=voice_agent,
                input=text
            )
            response.stream_to_file(speech_file_path)
            logic.sound_created = True
            gui.play_sound("generated_audio.mp3")
        else:
            print("Sound already created, playing it...")
            gui.play_sound("generated_audio.mp3")

class Logic:
    """A class to handle the main logic of the program"""
    def __init__(self) -> None:
        self.modus = None # modus keeps track of the training type that the user is currently in (DG, GD, RA, AI), mode will be used by other functions to determine the behavior of the program
        self.sound_created = False
        self.voice_model = "alloy"
        self.language_direction_ai = "DG"
        self.sentence_style_ai = "normal"

    @staticmethod
    def search_vocabulary_data()-> None:
        """
        Load vocabulary data with the following priority:
        1. SQLite DB exists with rows → load directly.
        2. Legacy JSON file exists → migrate to SQLite, then load.
        3. Legacy XLSX file exists → migrate to SQLite, then load.
        4. Nothing found → create an example SQLite DB and inform the user.
        """
        # Case 1: SQLite DB already populated
        if os.path.exists(config.DB_FILE):
            Data.init_db()
            conn = sqlite3.connect(config.DB_FILE)
            count = conn.execute('SELECT COUNT(*) FROM vocabulary').fetchone()[0]
            conn.close()
            if count > 0:
                Data.load_data_sqlite()
                return

        # Case 2: Migrate from JSON
        if os.path.exists(config.JSON_FILE):
            print("Migrating vocabulary from JSON to SQLite...")
            try:
                Data.load_data_json()
                Data.migrate_to_sqlite()
                Data.load_data_sqlite()
                return
            except Exception as e:
                print(f"JSON migration failed: {e}")

        # Case 3: Migrate from XLSX
        if os.path.exists(config.XLSX_FILE):
            print("Migrating vocabulary from XLSX to SQLite...")
            try:
                Data.load_and_check_xlsx(config.XLSX_FILE)
                Data.migrate_to_sqlite()
                Data.load_data_sqlite()
                return
            except Exception as e:
                print(f"XLSX migration failed: {e}")

        # Case 4: No data found — create example DB
        print("No vocabulary data found. Creating example database...")
        q_app = QApplication.instance() or QApplication(sys.argv)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Vocabulary File Missing")
        msg.setText(
            "<b style='font-size:16px; color:#d9534f;'>No vocabulary data found!</b><br><br>"
            "<span style='font-size:13px;'>An example database has been created.<br>"
            "Use <b>Manage Vocabulary</b> in the main menu to add your vocabulary.</span>"
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setStyleSheet("""
            QMessageBox { background-color: #f9f9f9; font-family: Arial; }
            QPushButton { min-width: 80px; min-height: 30px; font-size: 13px; }
        """)
        msg.exec()
        Data.init_db()
        conn = sqlite3.connect(config.DB_FILE)
        conn.execute("INSERT INTO vocabulary (dutch, german, note) VALUES ('hallo', 'hallo', 'ha-lo')")
        conn.execute("INSERT INTO vocabulary (dutch, german, note) VALUES ('de kat', 'die Katze', '')")
        conn.execute("INSERT INTO vocabulary (dutch, german, note) VALUES ('het huis', 'das Haus', '')")
        conn.commit()
        conn.close()
        Data.load_data_sqlite()
    
    @staticmethod
    def search_openai_api_key() -> str:
        """
        Try to load and return the OpenAI API key from environment variables.
        If it doesn't exist, inform the user and exit the program.
        """
        try:
            key = os.environ["OPENAI_API_KEY"]
        except KeyError:
            print("\n\nError: \nOPENAI_API_KEY not found in environment variables. Please set it and try again.\n\n")
            q_app = QApplication(sys.argv)
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("OpenAI API Key Missing")
            msg.setText(
                "<b style='font-size:16px; color:#d9534f;'>OPENAI_API_KEY not found!</b><br><br>"
                "<span style='font-size:13px;'>Please set your OpenAI API key as an environment variable named <b>OPENAI_API_KEY</b>.<br>"
                "You can do this in your system settings or via the command line.<br><br>"
                "<i>The program will exit now.</i></span>"
            )
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.setStyleSheet("""
                QMessageBox {
                    background-color: #f9f9f9;
                    font-family: Arial;
                }
                QPushButton {
                    min-width: 80px;
                    min-height: 30px;
                    font-size: 13px;
                }
            """)
            msg.exec()
            sys.exit()

    def choose_vocab(show_console_text: bool = True) -> int:
        """
        Choose the vocabulary to be asked next.
        Decision is based on three sublists:
            a.) how often was voc asked?
            b.) how correct (with how many slider points) was voc answered?
            c.) how long ago was voc asked?
        Special Cases:
            a.) When several vocs have the same score in a sublist, shuffle them randomly (otherwise they always get orderd by index and it gets boring).
            b.) Never ask the same item twice in a row (in fact an asked voc gets blocked for ten iterations).
        """

        def shuffle_list(list_to_shuffle: list) -> list:
            """Shuffle a list of lists based on the first element of each sublist."""
            # Group elements by value
            groups = {}
            for value, index in list_to_shuffle:
                if value not in groups:
                    groups[value] = []
                groups[value].append([value, index])

            # Shuffle elements within each group
            for value in groups:
                random.shuffle(groups[value])

            # Concatenate the groups back together
            shuffled_list = []
            for value in sorted(groups.keys()):
                shuffled_list.extend(groups[value])
            
            return shuffled_list
        
        def create_sublist_last_asked() -> list:
            """Create a sublist that sorts the vocabs by when they were last asked."""
            list_last_asked = [] # list that sorts the vocabs by when they were last asked
            for i in range(len(Data.last_asked)):
                # if the word was never asked, then add the date 01/01/2000 to the list
                if Data.last_asked[i] == "never":
                    list_last_asked.append(["01/01/2000", i])
                else:
                    list_last_asked.append([Data.last_asked[i], i])
            list_last_asked.sort(reverse=False)

            # shuffle the list make it a bit more random
            list_last_asked = shuffle_list(list_last_asked)
            if show_console_text: print("\nlist last asked: \n",list_last_asked)
            return list_last_asked
        
        def create_sublist_asked_often() -> list:
            """Create a sublist that sorts the vocabs by how often they were asked."""
            list_asked_often = [] # list that sorts the vocabs by how often it was asked
            for i in range(len(Data.asked)):
                list_asked_often.append([Data.asked[i], i])
            list_asked_often.sort(reverse=False)

            # shuffle the list make it a bit more random
            list_asked_often = shuffle_list(list_asked_often)
            if show_console_text: print("\nlist asked often: \n",list_asked_often)
            return list_asked_often
        
        def create_sublist_average_points() -> list:
            """Create a sublist that sorts the vocabs by how many points they got in the last 10 times they were asked."""
            list_average_points = [] # list that sorts the vocabs by how many points they got in the last 10 times they were asked
            for i in range(len(Data.points)):
                if len(Data.points[i]) > 10:
                    list_average_points.append([sum(Data.points[i][-10:])/10, i])
                elif len(Data.points[i]) > 0:
                    list_average_points.append([sum(Data.points[i])/len(Data.points[i]), i])
                else:
                    list_average_points.append([0, i])
            list_average_points.sort(reverse=False)

            # shuffle the list make it a bit more random
            list_average_points = shuffle_list(list_average_points)
            if show_console_text: print("\nlist average points: \n",list_average_points)
            return list_average_points
        
        def create_total_list() -> list:
            """Create a total list that combines the three sublists and gives each vocab a score."""
            # when you are the last vocab in a certain list, you get 1 point, second last 2 points, third last 3 points, etc.
            # the score of all three lists gets combined in list_total_score
            list_total_score = []
            # give weights to the three lists
            weight_last_asked = 1
            weight_asked_often = 1
            weight_average_points = 2

            for i in range(len(Data.dutch_voc_list)):
                score = 0
                for j in range(len(list_last_asked)):
                    if list_last_asked[j][1] == i:
                        score += (j * weight_last_asked)
                        break
                for j in range(len(list_asked_often)):
                    if list_asked_often[j][1] == i:
                        score += (j * weight_asked_often)
                        break
                for j in range(len(list_average_points)):
                    if list_average_points[j][1] == i:
                        score += (j * weight_average_points)
                        break
                list_total_score.append([score, i])
            list_total_score.sort(reverse=False)

            return list_total_score

        # create the sublists
        list_last_asked = create_sublist_last_asked()
        list_asked_often = create_sublist_asked_often()
        list_average_points = create_sublist_average_points()

        # create the total list
        list_total_score = create_total_list()

        # if no vocs were asked so far... we could take the first vocab from the list like chosen_vocab = list_total_score[0][1]
        # instead we go through the list and choose the first vocab that was not asked for at least 10 questions in this session
        for i in range(len(list_total_score)):
            if show_console_text: print("\nTen last session vocabs (blocked for taken as next vocab): ", Data.session_vocabs[-10:])
            if list_total_score[i][1] not in Data.session_vocabs[-10:]:
                chosen_vocab = list_total_score[i][1]
                if show_console_text: print("\nlist total score: \n",list_total_score)
                if show_console_text: print("\nNext vocab to ask: ", Data.dutch_voc_list[chosen_vocab], " with score ", list_total_score[i][0])
                break

        # save the selection in the session_vocabs
        try:
            Data.session_vocabs.append(chosen_vocab)
            # return the chosen vocab nr
            return chosen_vocab
        except:
            GUI.no_more_vocs(gui)
            #freeze application for 10 seconds
            time.sleep(10)
            # stop the program
            sys.exit()

    def ask_question() -> tuple: 
        """Ask a question by choosing a random vocabulary and returning the Dutch word, its correct translation, phonetics, and the vocabulary number."""
        global vocab_nr
        vocab_nr = Logic.choose_vocab()
        # alternatively random vocab selection:
        #vocab_nr = random.randint(0, len(DataHandler.data_frame[0])-1)
        print(vocab_nr)
        print(Data.data_frame[0])

        print(Data.data_frame[0][vocab_nr], " - ", Data.data_frame[1][vocab_nr])
        dutch_word = Data.data_frame[0][vocab_nr]
        correct_translation = Data.data_frame[1][vocab_nr]
        phonetics = Data.data_frame[2][vocab_nr]

        return dutch_word, correct_translation, phonetics, vocab_nr
    
    def short_lines(text: str, pixel: int = 500) -> str:
        """
        Divide a long text into multiple lines based on a character limit.
        The limit is 30 characters for pixel=500 and 65 characters for pixel=800.
        """
        words = text.split()  # Split the input text into words
        lines = []  # List to store the lines

        current_line = ""  # Initialize an empty line
        for word in words:
            # Check if adding the word to the current line exceeds the 30 character limit
            if pixel == 500:
                if len(current_line) + len(word) + 1 <= 30:
                    if current_line == "":
                        current_line = word
                    else:
                        current_line += " " + word
                else:
                    lines.append(current_line)  # Add the current line to the list of lines
                    current_line = word  # Start a new line with the current word
            elif pixel == 800:
                if len(current_line) + len(word) + 1 <= 65:
                    if current_line == "":
                        current_line = word
                    else:
                        current_line += " " + word
                else:
                    lines.append(current_line)
                    current_line = word
        
        # Add the last line (if any) to the list of lines
        if current_line:
            lines.append(current_line)

        # Join the lines with newline characters to get the final output
        text_output = "\n".join(lines)
        
        return text_output

    def create_statistics_data() -> pd.DataFrame:
        """Create a DataFrame with statistics about the vocabulary training (None = no answers yet)."""

        def average(points: list) -> float | None:
            return sum(points)/len(points) if points else None

        data_list = []
        for i in range(len(Data.dutch_voc_list)):
            data_list.append([
                Data.dutch_voc_list[i],
                Data.german_voc_list[i],
                Data.phonetics_list[i],
                Data.asked[i],
                Data.correct[i],
                Data.wrong[i],
                average(Data.points[i]),
                average(Data.points[i][-10:]),
                average(Data.d_g_points[i]),
                average(Data.g_d_points[i]),
                "  ".join(str(round(p)) for p in Data.points[i][-5:]) or "—",
                Data.last_asked[i]
            ])

        table_data = pd.DataFrame(data_list, columns=['Dutch', 'German', 'Note', 'Asked', 'Correct', 'Wrong', 'Avg', 'Avg Last 10', 'Avg NL→DE', 'Avg DE→NL', 'Last 5 Scores', 'Last Asked'])
        # keep None (not NaN) for missing averages so the table can show a dash
        table_data = table_data.astype(object).where(table_data.notna(), None)

        return table_data

# MAIN

def main():
    # check if vocabulary data is available, if not, create an example file
    Logic.search_vocabulary_data()
    # check if OpenAI API key is available, if not exit
    Logic.search_openai_api_key()

    # add todays date to current_date
    Data.add_current_date()

    # initialize the open ai client to generate AI sentences
    global aiapi
    aiapi = AiApi()

    # initialize the Logic class
    global logic
    logic = Logic()

    # initialize the user interface
    global gui
    gui = GUI()
    gui.run()

if __name__ == "__main__":
    main()