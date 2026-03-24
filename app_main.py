
# IMPORTS

import datetime
import json
import os
from openai import OpenAI
import pandas as pd
import random
import sys
import time
from pygame import mixer
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QSlider, QTableView, QComboBox, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QCoreApplication
import openpyxl

# MODULE IMPORTS

import config

# CLASSES

class Table(QAbstractTableModel):
    """A class to create a standard table model for the statistics table"""
    def __init__(self, data: pd.DataFrame) -> None:
        super().__init__()
        self._data = data

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data.columns)

    def data(self, index: QModelIndex, role: Qt.ItemDataRole) -> str | None:
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole) -> str | None:
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])
            if orientation == Qt.Orientation.Vertical:
                return str(self._data.index[section])
        return None

    def sort(self, column: int, order: Qt.SortOrder) -> None:
        self.layoutAboutToBeChanged.emit()
        if order == Qt.SortOrder.AscendingOrder:
            self._data = self._data.sort_values(by=self._data.columns[column], ascending=True)
        else:
            self._data = self._data.sort_values(by=self._data.columns[column], ascending=False)
        self.layoutChanged.emit()

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

class Data:
    """A class to handle (load, save, manipulate) the data of the vocabulary"""
    data_frame = []         # nested list with all data combined
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

class GUI:
    """A class to handle the user interface with pyqt"""
    STYLESHEET = """
        * {
            font-family: "Segoe UI", Arial, sans-serif;
        }
        QMainWindow {
            background-color: #F5F6F8;
        }
        QWidget {
            background-color: #F5F6F8;
        }
        QPushButton {
            background-color: #2C3E50;
            color: #FFFFFF;
            border: none;
            border-radius: 6px;
            padding: 12px 24px;
            font-size: 15px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #34495E;
        }
        QPushButton:pressed {
            background-color: #1A252F;
        }
        QLabel {
            color: #2C3E50;
            background-color: transparent;
        }
        QLabel#card {
            background-color: #FFFFFF;
            border: 1px solid #E0E4E8;
            border-radius: 10px;
            padding: 20px;
        }
        QLabel#info {
            background-color: #FFFFFF;
            border: 1px solid #E0E4E8;
            border-radius: 10px;
            padding: 20px;
            color: #5A6A7A;
        }
        QSlider::groove:horizontal {
            height: 6px;
            background: #E0E4E8;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #2C3E50;
            border: 2px solid #FFFFFF;
            width: 20px;
            height: 20px;
            margin: -8px 0;
            border-radius: 11px;
        }
        QSlider::handle:horizontal:hover {
            background: #3498DB;
        }
        QSlider::sub-page:horizontal {
            background: #3498DB;
            border-radius: 3px;
        }
        QComboBox {
            background-color: #FFFFFF;
            color: #2C3E50;
            border: 1px solid #E0E4E8;
            border-radius: 6px;
            padding: 10px 16px;
            font-size: 15px;
        }
        QComboBox:hover {
            border-color: #3498DB;
        }
        QComboBox::drop-down {
            border: none;
            width: 30px;
        }
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid #2C3E50;
            margin-right: 10px;
        }
        QComboBox QAbstractItemView {
            background-color: #FFFFFF;
            border: 1px solid #E0E4E8;
            border-radius: 4px;
            selection-background-color: #EBF5FB;
            selection-color: #2C3E50;
            padding: 4px;
        }
        QTableView {
            background-color: #FFFFFF;
            border: 1px solid #E0E4E8;
            border-radius: 8px;
            gridline-color: #F0F2F5;
            selection-background-color: #EBF5FB;
            selection-color: #2C3E50;
            font-size: 13px;
        }
        QTableView::item {
            padding: 6px 10px;
        }
        QHeaderView::section {
            background-color: #F5F6F8;
            color: #2C3E50;
            font-weight: 600;
            font-size: 13px;
            border: none;
            border-bottom: 2px solid #E0E4E8;
            padding: 8px 10px;
        }
        QHeaderView::section:hover {
            background-color: #EBF5FB;
        }
        QMessageBox {
            background-color: #F5F6F8;
        }
        QMessageBox QPushButton {
            min-width: 90px;
            min-height: 34px;
        }
    """

    def __init__(self) -> None:
        # initialize the pygame mixer for playing sound files
        mixer.init()

        self.app = QApplication([])
        self.app.setStyleSheet(GUI.STYLESHEET)
        self.window = QMainWindow()
        self.start_main_menu()

    def start_main_menu(self) -> None:
        """Set up the main menu as part of the GUI."""
        central_widget = QWidget()
        self.window.setCentralWidget(central_widget)

        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        layout.setSpacing(14)

        # Title
        title_label = QLabel('Vocabulary Trainer')
        title_label.setFont(QFont("Segoe UI", 28, QFont.Weight.Light))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("color: #2C3E50; margin-bottom: 30px;")
        layout.addWidget(title_label)

        button_width = 280
        button_height = 52

        self.start_training_button = QPushButton('Start Training')
        self.start_training_button.setFixedSize(button_width, button_height)

        self.explore_statistics_button = QPushButton('Explore Statistics')
        self.explore_statistics_button.setFixedSize(button_width, button_height)

        self.refresh_vocabulary_button = QPushButton('Refresh Vocabulary List')
        self.refresh_vocabulary_button.setFixedSize(button_width, button_height)

        layout.addWidget(self.start_training_button)
        layout.addWidget(self.explore_statistics_button)
        layout.addWidget(self.refresh_vocabulary_button)

        central_widget.setLayout(layout)

        self.start_training_button.clicked.connect(self.select_training_type)
        self.explore_statistics_button.clicked.connect(self.explore_statistics)
        self.refresh_vocabulary_button.clicked.connect(self.refresh_vocabulary)

        self.window.setWindowTitle('Vocabulary Trainer')
        self.window.showMaximized()

    def select_training_type(self) -> None:
        """Set up the training type selection screen as part of the GUI."""
        
        # three buttons, one for Dutch -> German, one for German -> Dutch, Random; they launch the respective functions

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        button_width = 320
        button_height = 52

        button_dutch_german = QPushButton('Dutch \u2192 German')
        button_dutch_german.setFixedSize(button_width, button_height)
        layout.addWidget(button_dutch_german)

        button_german_dutch = QPushButton('German \u2192 Dutch')
        button_german_dutch.setFixedSize(button_width, button_height)
        layout.addWidget(button_german_dutch)

        button_random = QPushButton('Random')
        button_random.setFixedSize(button_width, button_height)
        layout.addWidget(button_random)

        button_advanced_mode = QPushButton('Advanced Mode')
        button_advanced_mode.setFixedSize(button_width, button_height)
        layout.addWidget(button_advanced_mode)

        # refresh the window
        self.window.update()

        # Connect button clicks to their respective functions
        button_dutch_german.clicked.connect(self.start_dutch_german)
        button_german_dutch.clicked.connect(self.start_german_dutch)
        button_random.clicked.connect(self.start_random)
        button_advanced_mode.clicked.connect(self.start_advanced_mode)

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
                # remove button change_screen
                layout.removeWidget(button_end_training)
                button_end_training.deleteLater()  # Delete the widget
                # add button confirm_selection
                layout.addWidget(button_next_vok)
                # add slider to evaluate how well the translation was known
                self.slider = QSlider(Qt.Orientation.Horizontal)
                self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
                self.slider.setTickInterval(1)
                self.slider.setMinimum(0)
                self.slider.setMaximum(100)
                self.slider.setSingleStep(1)
                self.slider.setPageStep(10)
                self.slider.setSliderPosition(50)
                self.slider.setFixedSize(500, 60) # width, height
                self.slider.setFont(QFont("Arial", 16))
                layout.addWidget(self.slider)
                # nonlocal slider_added
                slider_added = True

                #update screen  
                self.window.update()

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
            Data.save_data_json()
            # ask for a new vocab
            GUI.start_dutch_german(self)

        # SET UP THE LAYOUT

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        dutch_word, correct_translation, phonetics, vocab_nr = Logic.ask_question()

        label_text = Logic.short_lines(dutch_word)+"\n"+phonetics
        label = QLabel(label_text, self.window, alignment=Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("card")
        label.setFont(QFont("Segoe UI", 22, QFont.Weight.Light))
        label.setFixedSize(500, 280)

        button_translate = QPushButton('Show Translation')
        button_translate.setFixedSize(500, 52)

        button_end_training = QPushButton('End Training')
        button_end_training.setFixedSize(500, 52)

        button_next_vok = QPushButton('Next Vocabulary')
        button_next_vok.setFixedSize(500, 52)

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
                # remove button change_screen
                layout.removeWidget(button_end_training)
                button_end_training.deleteLater()  # Delete the widget
                # add button confirm_selection
                layout.addWidget(button_next_vok)
                # add slider to evaluate how well the translation was known
                self.slider = QSlider(Qt.Orientation.Horizontal)
                self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
                self.slider.setTickInterval(1)
                self.slider.setMinimum(0)
                self.slider.setMaximum(100)
                self.slider.setSingleStep(1)
                self.slider.setPageStep(10)
                self.slider.setSliderPosition(50)
                self.slider.setFixedSize(500, 60) # width, height
                self.slider.setFont(QFont("Arial", 16))
                layout.addWidget(self.slider)
                # nonlocal slider_added
                slider_added = True

                #update screen  
                self.window.update()
        
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
            Data.save_data_json()
            # ask for a new vocab
            GUI.start_german_dutch(self)

        # SET UP THE LAYOUT

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Create a QLabel with vocabulary to ask
        dutch_word, correct_translation, phonetics, vocab_nr = Logic.ask_question()
        german_word = correct_translation

        # ToDo: if phenetics is empty, don't show it
        label_text = Logic.short_lines(german_word)
        label = QLabel(label_text, self.window, alignment=Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Times New Roman", 24))
        label.setFixedSize(500,300) # width, height
        #set border 
        label.setStyleSheet("border: 1px solid black;")

        # create a button under the label to show the correct translation
        button_translate = QPushButton('Show Translation')
        button_translate.setFixedSize(500, 60) # width, height
        button_translate.setFont(QFont("Arial", 16))
        
        button_end_training = QPushButton('End Training')
        button_end_training.setFixedSize(500, 60) # width, height
        button_end_training.setFont(QFont("Arial", 16))

        button_next_vok = QPushButton('Next Vocabulary')
        button_next_vok.setFixedSize(500, 60) # width, height
        button_next_vok.setFont(QFont("Arial", 16))

        # Add the label to the layout
        layout.addWidget(label)
        # put button 100 px more to the right
        layout.addWidget(button_translate)
        layout.addWidget(button_end_training) #, alignment=Qt.AlignmentFlag.AlignBottom

        # # Connect button clicks to their respective functions
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
                # remove button change_screen
                layout.removeWidget(button_end_training)
                button_end_training.deleteLater()  # Delete the widget
                # add button confirm_selection
                layout.addWidget(button_next_vok)
                # add slider to evaluate how well the translation was known
                self.slider = QSlider(Qt.Orientation.Horizontal)
                self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
                self.slider.setTickInterval(1)
                self.slider.setMinimum(0)
                self.slider.setMaximum(100)
                self.slider.setSingleStep(1)
                self.slider.setPageStep(10)
                self.slider.setSliderPosition(50)
                self.slider.setFixedSize(500, 60) # width, height
                self.slider.setFont(QFont("Arial", 16))
                layout.addWidget(self.slider)
                # nonlocal slider_added
                slider_added = True

                #update screen  
                self.window.update()
        
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
            Data.save_data_json()
            # ask for a new vocab
            GUI.start_random(self)

        # SET UP THE LAYOUT

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Create a QLabel with vocabulary to ask
        dutch_word, correct_translation, phonetics, vocab_nr = Logic.ask_question()

        # ToDo: if phenetics is empty, don't show it
        if random.randint(0,1) == 0:
            label_text = Logic.short_lines(dutch_word)+"\n"+phonetics
        else:
            label_text = Logic.short_lines(correct_translation)
        label = QLabel(label_text, self.window, alignment=Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Times New Roman", 24))
        label.setFixedSize(500,300) # width, height
        #set border 
        label.setStyleSheet("border: 1px solid black;")

        # create a button under the label to show the correct translation
        button_translate = QPushButton('Show Translation')
        button_translate.setFixedSize(500, 60) # width, height
        button_translate.setFont(QFont("Arial", 16))
        
        button_end_training = QPushButton('End Training')
        button_end_training.setFixedSize(500, 60) # width, height
        button_end_training.setFont(QFont("Arial", 16))

        button_next_vok = QPushButton('Next Vocabulary')
        button_next_vok.setFixedSize(500, 60) # width, height
        button_next_vok.setFont(QFont("Arial", 16))

        # Add the label to the layout
        layout.addWidget(label)
        # put button 100 px more to the right
        layout.addWidget(button_translate)
        layout.addWidget(button_end_training) #, alignment=Qt.AlignmentFlag.AlignBottom

        # # Connect button clicks to their respective functions
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
                # remove button change_screen
                layout.removeWidget(button_end_training)
                button_end_training.deleteLater()  # Delete the widget
                # add button confirm_selection
                layout.addWidget(button_next_vok)
                # add slider to evaluate how well the translation was known
                self.slider = QSlider(Qt.Orientation.Horizontal)
                self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
                self.slider.setTickInterval(1)
                self.slider.setMinimum(0)
                self.slider.setMaximum(100)
                self.slider.setSingleStep(1)
                self.slider.setPageStep(10)
                self.slider.setSliderPosition(50)
                self.slider.setFixedSize(800, 60) # width, height
                self.slider.setFont(QFont("Arial", 16))
                layout.addWidget(self.slider)
                # nonlocal slider_added
                slider_added = True

                #update screen  
                self.window.update()
        
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
            Data.save_data_json()
            # ask for a new vocab
            GUI.start_ai_sentences(self)

        # SET UP THE LAYOUT

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Create a QLabel with vocabulary to ask
        dutch_word, correct_translation, phonetics, vocab_nr = Logic.ask_question()

        label_text = Logic.short_lines(dutch_word)+"\n"+phonetics
        label = QLabel(label_text, self.window, alignment=Qt.AlignmentFlag.AlignCenter)
        label.setFont(QFont("Times New Roman", 24))
        label.setFixedSize(800,200) # width, height
        #set border 
        label.setStyleSheet("border: 1px solid black;")

        # generate data with AI
        ai_sentence = AiApi.generate_AI_sentence(dutch_word, aiapi.OpenAiClient)
        ai_sentence_translation = "Dies ist ein Test, um zu sehen, wie das Programm die visuelle Darstellung eines längeren Satzes handhabt. Es sollte in der Lage sein, den ganzen Satz anzuzeigen und ihn nicht abzuschneiden. Der Satz sollte in der Mitte des Fensters angezeigt werden." #TODO
        ai_sentence_translation = AiApi.generate_AI_translation(ai_sentence, aiapi.OpenAiClient)
        logic.sound_created = False
        
        # Create second Qlabel, which will show the AI sentence
        label_text_ai = Logic.short_lines(ai_sentence, pixel=800)
        label_ai_sentence = QLabel(label_text_ai, self.window, alignment=Qt.AlignmentFlag.AlignCenter)
        label_ai_sentence.setFont(QFont("Times New Roman", 20))
        label_ai_sentence.setFixedSize(800,300) # width, height
        #set border
        label_ai_sentence.setStyleSheet("border: 1px solid black;")

        # create a button under the label to show the correct translation
        button_translate = QPushButton('Show Translation')
        button_translate.setFixedSize(800, 60) # width, height
        button_translate.setFont(QFont("Arial", 16))
        
        button_end_training = QPushButton('End Training')
        button_end_training.setFixedSize(800, 60) # width, height
        button_end_training.setFont(QFont("Arial", 16))

        button_next_vok = QPushButton('Next Vocabulary')
        button_next_vok.setFixedSize(800, 60) # width, height
        button_next_vok.setFont(QFont("Arial", 16))

        button_play_sound = QPushButton('Play Sound')
        button_play_sound.setFixedSize(800, 60)
        button_play_sound.setFont(QFont("Arial", 16))

        # Add the label to the layout
        layout.addWidget(label)
        layout.addWidget(label_ai_sentence)
        # put button 100 px more to the right
        layout.addWidget(button_translate)
        layout.addWidget(button_play_sound)
        layout.addWidget(button_end_training) #, alignment=Qt.AlignmentFlag.AlignBottom

        # Connect button clicks to their respective functions
        button_translate.clicked.connect(show_translation)
        button_end_training.clicked.connect(self.end_training)
        button_next_vok.clicked.connect(next_vocab)
        button_play_sound.clicked.connect(lambda: AiApi.text_to_speech(ai_sentence, aiapi.OpenAiClient, logic.voice_model))

        # refresh the window
        self.window.update()

    def start_advanced_mode(self) -> None:
        """Set up the advanced mode screen with dropdowns for voice model, language direction, and sentence style."""
        logic.modus = "SE" # change the modus to settings
        # set all dropdowns to the first option in the logic_handler
        logic.voice_model = "alloy"
        logic.language_direction_ai = "DG"
        logic.sentence_style_ai = "normal"

        # SET UP THE LAYOUT

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # create a dropdown menu for chosing the voice model and add it to the layout
        self.voice_model_dropdown = QComboBox(self.window)
        self.voice_model_dropdown.addItem(" Voice Model:\tAlloy")
        self.voice_model_dropdown.addItem(" Voice Model:\tEcho")
        self.voice_model_dropdown.addItem(" Voice Model:\tFable")
        self.voice_model_dropdown.addItem(" Voice Model:\tNova")
        self.voice_model_dropdown.addItem(" Voice Model:\tOnyx")
        self.voice_model_dropdown.addItem(" Voice Model:\tShimmer")

        self.voice_model_dropdown.setFixedSize(500, 60) # width, height
        self.voice_model_dropdown.setFont(QFont("Arial", 16))
        layout.addWidget(self.voice_model_dropdown)

        # create a dropdown menu for chosing the language and add it to the layout
        self.language_dropdown = QComboBox(self.window)
        self.language_dropdown.addItem(" Language:\tDutch -> German")
        self.language_dropdown.addItem(" Language:\tGerman -> Dutch")

        self.language_dropdown.setFixedSize(500, 60) # width, height
        self.language_dropdown.setFont(QFont("Arial", 16))
        layout.addWidget(self.language_dropdown)

        # create a dropdown menu for chosing the sentence style and add it to the layout
        self.sentence_style_dropdown = QComboBox(self.window)
        self.sentence_style_dropdown.addItem(" Sentence Style:\tNormal")
        self.sentence_style_dropdown.addItem(" Sentence Style:\tScientific")
        self.sentence_style_dropdown.addItem(" Sentence Style:\tScary")
        self.sentence_style_dropdown.addItem(" Sentence Style:\tOffensive")

        self.sentence_style_dropdown.setFixedSize(500, 60) # width, height
        self.sentence_style_dropdown.setFont(QFont("Arial", 16))
        layout.addWidget(self.sentence_style_dropdown)

        # create a button to start the training and add it to the layout
        button_start_advanced_training = QPushButton('Start Training')
        button_start_advanced_training.setFixedSize(500, 60) # width, height
        button_start_advanced_training.setFont(QFont("Arial", 16))
        layout.addWidget(button_start_advanced_training)

        # Connect the signals to the slots
        self.voice_model_dropdown.currentIndexChanged.connect(self.on_voice_model_change)
        self.language_dropdown.currentIndexChanged.connect(self.on_language_change)
        self.sentence_style_dropdown.currentIndexChanged.connect(self.on_sentence_style_change)
        button_start_advanced_training.clicked.connect(self.start_ai_sentences)

    def on_voice_model_change(self, index) -> None:
        """Change the voice model based on the selected index in the dropdown."""
        # set the voice model in the logic_handler
        logic.voice_model = self.voice_model_dropdown.itemText(index)
        #change to file folder
        os.chdir(config.FILES_PATH)
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
        # back to main folder
        os.chdir(config.MAIN_PATH)

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

        def back_to_main_menu():
            GUI.start_main_menu(self)
        
        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # transform all data into a table form
        table_data = Logic.create_statistics_data()

        # Create a pyqt table with that data
        table = QTableView()
        model = Table(table_data)
        table.setModel(model)

        # Enable sorting
        table.setSortingEnabled(True)
        layout.addWidget(table)
        # Connect header click event to trigger sorting
        table.horizontalHeader().sectionClicked.connect(lambda index: model.sort(index, table.horizontalHeader().sortIndicatorOrder()))

        # add a button to go back to the main menu
        button_back_to_main_menu = QPushButton('Main Menu')
        width_of_screen = self.window.frameGeometry().width()
        button_back_to_main_menu.setFixedSize(width_of_screen-20, 35) # width, height
        button_back_to_main_menu.setFont(QFont("Arial", 12))
        layout.addWidget(button_back_to_main_menu)
        button_back_to_main_menu.clicked.connect(back_to_main_menu)

        # refresh the window
        self.window.update()

    def refresh_vocabulary(self) -> None:
        """Refresh the vocabulary by loading the data from the xlsx file."""
        # SET UP THE LAYOUT

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        self.window.update()

        # show message that the vocabulary is being refreshed
        info_label = QLabel("Refreshing vocabulary...", self.window, alignment=Qt.AlignmentFlag.AlignCenter)
        info_label.setFont(QFont("Times New Roman", 24))
        info_label.setFixedSize(500,300) # width, height
        #set border
        info_label.setStyleSheet("border: 1px solid black;")
        layout.addWidget(info_label)
        # layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)  # Center horizontally

        # force the program to show the label (otherwise it will only show it after the vocabulary is refreshed)
        info_label.setStyleSheet("background-color: #f0f0f0;")
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

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        self.window.update()

        # show message that the vocabulary is being refreshed
        info_label = QLabel("Congrats! All Vocabularies were trained once!\nThe program will end now.", self.window, alignment=Qt.AlignmentFlag.AlignCenter)
        info_label.setFont(QFont("Times New Roman", 24))
        info_label.setFixedSize(900,900) # width, height
        #set border
        info_label.setStyleSheet("border: 1px solid black;")
        layout.addWidget(info_label)
        # layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)  # Center horizontally

        # force the program to show the label (otherwise it will only show it after the vocabulary is refreshed)
        info_label.setStyleSheet("background-color: #f0f0f0;")
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
        Try to load vocabulary from json file, if it doesn't exist, then load it from xlsx file.
        If neither exists, create an example xlsx file, explain to the user, open it for the user and exit the program.
        """
        try:
            Data.data_frame = Data.load_data_json()
        except FileNotFoundError:
            print("\n\nNo vocabulary data found as json. Trying to load it from xlsx file.\n")
            try:
                Data.load_and_check_xlsx(config.XLSX_FILE)
            except Exception:
                print("\n\nError: \nNo vocabulary data found as json or xlsx. An example file with the name 'VOCABS.xlsx' will be created in the '/files' directory, fill in your Vocabulary there.\nThe program will exit after creating the new file.\n\n")
                q_app = QApplication(sys.argv)
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Vocabulary File Missing")
                msg.setText(
                    "<b style='font-size:16px; color:#d9534f;'>No vocabulary data found!</b><br><br>"
                    "<span style='font-size:13px;'>An example file named <b>'VOCABS.xlsx'</b> will be created in the <b>'/files'</b> directory.<br>"
                    "Please fill in your vocabulary there.<br><br>"
                    "<i>The program will exit after creating the new file.</i></span>"
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
                Data.create_empty_xlsx(config.XLSX_FILE)
                os.startfile(os.path.abspath(config.XLSX_FILE))
                sys.exit()
    
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
            GUI.no_more_vocs(GUI.instance[0])
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
        """Create a DataFrame with statistics about the vocabulary training."""
        data_list = []

        # create a list that tells how many points the vocs have on average
        average_points = []
        for i in range(len(Data.points)):
            if len(Data.points[i]) > 0:
                average_points.append(round(sum(Data.points[i])/len(Data.points[i]), 2))
            else:
                average_points.append(0)
        # create a list that tell how many points the vocs have on average in the last 10 times they were asked
        average_points_last_10 = []
        for i in range(len(Data.points)):
            if len(Data.points[i]) > 10:
                average_points_last_10.append(round(sum(Data.points[i][-10:])/10, 2))
            elif len(Data.points[i]) > 0:
                average_points_last_10.append(round(sum(Data.points[i])/len(Data.points[i]), 2))
            else:
                average_points_last_10.append(0)
        # calculate the average points for dutch->german and german->dutch translations
        average_points_d_g = []
        average_points_g_d = []
        for i in range(len(Data.d_g_points)):
            if len(Data.d_g_points[i]) > 0:
                average_points_d_g.append(round(sum(Data.d_g_points[i])/len(Data.d_g_points[i]), 2))
            else:
                average_points_d_g.append(0)
        for i in range(len(Data.g_d_points)):
            if len(Data.g_d_points[i]) > 0:
                average_points_g_d.append(round(sum(Data.g_d_points[i])/len(Data.g_d_points[i]), 2))
            else:
                average_points_g_d.append(0)

        for i in range(len(Data.dutch_voc_list)):
            data_list.append([
                Data.dutch_voc_list[i], 
                Data.german_voc_list[i], 
                Data.phonetics_list[i], 
                Data.asked[i], 
                Data.correct[i], 
                Data.wrong[i], 
                Data.points[i],
                average_points[i],
                average_points_last_10[i],
                Data.d_g_points[i],
                average_points_d_g[i],
                Data.g_d_points[i], 
                average_points_g_d[i],
                Data.last_asked[i]
            ])

        table_data = pd.DataFrame(data_list, columns=['Dutch', 'German', 'Phonetics', 'Asked', 'Correct', 'Wrong', 'Points', 'Average Points', 'Average Points Last 10', 'Points D->G','Average Points D->G', 'Points G->D', 'Average Points G->D', 'Last Asked'])

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