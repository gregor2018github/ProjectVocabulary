"""
ToDo:
- add a slider to evaluate how well the translation was known                                                                        [done]
- add a button to end the training                                                                                                   [done]
- add a button to continue with the next vocab                                                                                       [done]
- add a button to go back to the main menu                                                                                           [done]
- refresh the vocabulary list functionally                                                                                           [done]
- select the vocs based on a point system and not randomly                                                                           [done]
- divide the text into several lines if it is too long                                                                               [done]
- vocab selection on point system scharf schalten                                                                                    [done]
- vocab may only be repeated once per 10 vocs                                                                                        [done]
- create statistics to visiualize the learning progress                                                                              [done]
- go back from stats to main menu                                                                                                    [done]
- rethink how to handle altered translations while loading the vocabulary from docx file                                             [done]
- learn to make it executable (folder management, turn off console text)                                                             [done]
- add top description to the code                                                                                                    [done]
- optimize selection of vocs                                                                                                         [done]
    -   randomize the order of vocs with same stats in certain criteria                                                                    [done]
    -   give more emphasis to correctness (either with right and wrong or with points)                                                     [done]
- give possibility to translate from "german -> dutch" and "random"                                                                  [done]


Description:
This program is a vocabulary trainer for Dutch and German words. It loads the vocabulary from a DUTCH.docx file and saves the statistics in a vocabulary_data.json file.
The user interface is created with pyqt6. Key feature is a slider to evaluate how well the translation was known (right=good, left=bad). The statistics are visualized in a table.
Translations are possible in both directions. 
The program chooses the next word based on how often it was asked, how correct it was answered and how long ago it was asked.
The program also never asks the same word twice in a session of 10 words.
The program can start with a json file or with a docx file. If there is no json file, then the docx file is loaded and a json file is created.
The vocabulary can constantly be enlarged by adding new words to the end of the docx file. Also translations can be changed. The order of rows may not be changed though.
The main menu has a button to refresh the vocabulary list from the docx file while keeping the statistics from the json file.

"""

import datetime
import json
import os
import pandas as pd
import random
import sys
from docx import Document
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel, QSlider, QTableView
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QCoreApplication

# class that creates a table model for the statistics table
class TableModel(QAbstractTableModel):
    def __init__(self, data):
        super().__init__()
        self._data = data

    def rowCount(self, parent=QModelIndex()):
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        return len(self._data.columns)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            return str(self._data.iloc[index.row(), index.column()])
        return None

    def headerData(self, section, orientation, role):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return str(self._data.columns[section])
            if orientation == Qt.Orientation.Vertical:
                return str(self._data.index[section])
        return None
    
    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        if order == Qt.SortOrder.AscendingOrder:
            self._data = self._data.sort_values(by=self._data.columns[column], ascending=True)
        else:
            self._data = self._data.sort_values(by=self._data.columns[column], ascending=False)
        self.layoutChanged.emit()

    def flags(self, index):
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled

# class to handle (load, save, manipulate) the data of the vocabulary
class DataHandler:
    data_frame = []         # nested list with all data combined
    dutch_voc_list = []     # df[0]: dutch word
    german_voc_list = []    # df[1]: german translation of the dutch word
    phonetics_list = []     # df[2]: phonetics of the dutch word
    asked = []              # df[3]: how often was the word asked, one integer per word
    correct = []            # df[4]: how often was the word answered correctly (> 60 points), one integer per word
    wrong = []              # df[5]: how often was the word answered wrong (< 40 points), one integer per word
    points = []             # df[6]: how secure was the trainee with the word, several doubles per word
    last_asked = []         # df[7]: when was the word asked the last time, one date per word
    current_date = []       # df[8]: current date, gets updated every time the program is started
    session_vocabs = []     # temporary storage of what vocabs where asked this session

    # open a docx file and load the vocabulary table into three lists (dutch, german, phonetics)
    def load_docx(filename):
        print("Loading vocabulary from docx file...")
        # load tables from document
        document = Document(filename)

        # iterate over all tables in the document and merge them into one list
        voc_table = []
        for table in document.tables:
            voc_table.extend(table.rows)
        
        temp_dutch_voc_list = []    # temporary list to store the dutch words
        temp_german_voc_list = []   # temporary list to store the german words
        temp_phonetics_list = []    # temporary list to store the phonetics

        # isolate dutch words as a list
        for i in range(len(voc_table)):
            if voc_table[i].cells[0].text != "": # only if column one is not empty
                temp_dutch_voc_list.append(voc_table[i].cells[0].text)
                temp_german_voc_list.append(voc_table[i].cells[1].text)
                temp_phonetics_list.append(voc_table[i].cells[2].text)

        # when there is no file vacabulary_data.json, then save the lists as the DataHandler lists / df
        if not os.path.exists('vocabulary_data.json'):
            print("No json data found. Creating new json data...")
            DataHandler.dutch_voc_list = temp_dutch_voc_list
            DataHandler.german_voc_list = temp_german_voc_list
            DataHandler.phonetics_list = temp_phonetics_list
            DataHandler.asked = [0] * len(temp_dutch_voc_list)
            DataHandler.correct = [0] * len(temp_dutch_voc_list)
            DataHandler.wrong = [0] * len(temp_dutch_voc_list)
            for i in range(len(temp_dutch_voc_list)):
                DataHandler.points.append([])
            DataHandler.last_asked = ["never"] * len(temp_dutch_voc_list)
            DataHandler.current_date = [datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")]

            # combine dutch, german and phonetics list into a nested list, the data frame
            DataHandler.data_frame = [DataHandler.dutch_voc_list, DataHandler.german_voc_list, DataHandler.phonetics_list, DataHandler.asked, DataHandler.correct, DataHandler.wrong, DataHandler.points, DataHandler.last_asked, DataHandler.current_date]

        """The rows must barely be changed (row 1 must always be reserved for the same vocabulary but we might slightly alter the dutch or german writing).
            Pseudocode:
            if same amount of rows in docx and json:
            -> check for each row if german or dutch translation is altered
            -> if yes change it in the json

            elif more rows in docx than in json:
            -> add additional rows of docx to json and give them default values for asked, correct, wrong, points, last_asked

            elif less rows in docx than in json
            -> throw error and end program without saving data
            
            Actual Code:"""
        
        # when there is a file vacabulary_data.json, then load the lists from the file
        if os.path.exists('vocabulary_data.json'):
            # if same amount of rows in docx and json:
            if len(temp_dutch_voc_list) == len(DataHandler.dutch_voc_list):
                for i in range(len(temp_dutch_voc_list)):
                    # check for each row if dutch translation is altered
                    if temp_dutch_voc_list[i] != DataHandler.dutch_voc_list[i]:
                        print("New dutch description'", temp_dutch_voc_list[i], "' It will be added to the vocabulary list.")
                        DataHandler.dutch_voc_list[i] = temp_dutch_voc_list[i]
                    # check for each row if german translation is altered
                    if temp_german_voc_list[i] != DataHandler.german_voc_list[i]:
                        print("New german translation found for '", temp_dutch_voc_list[i], "' It will be added to the vocabulary list.")
                        DataHandler.german_voc_list[i] = temp_german_voc_list[i]
                    # check for each row if phonetics is altered
                    if temp_phonetics_list[i] != DataHandler.phonetics_list[i]:
                        print("New phonetics found for '", temp_dutch_voc_list[i], "' It will be added to the vocabulary list.")
                        DataHandler.phonetics_list[i] = temp_phonetics_list[i]
            # elif more rows in docx than in json:
            elif len(temp_dutch_voc_list) > len(DataHandler.dutch_voc_list):
                for i in range(len(DataHandler.dutch_voc_list), len(temp_dutch_voc_list)):
                    print("New word found: '", temp_dutch_voc_list[i], "' It will be added to the vocabulary list.")
                    DataHandler.dutch_voc_list.append(temp_dutch_voc_list[i])
                    DataHandler.german_voc_list.append(temp_german_voc_list[i])
                    DataHandler.phonetics_list.append(temp_phonetics_list[i])
                    DataHandler.asked.append(0)
                    DataHandler.correct.append(0)
                    DataHandler.wrong.append(0)
                    DataHandler.points.append([])
                    DataHandler.last_asked.append("never")
            # elif less rows in docx than in json
            elif len(temp_dutch_voc_list) < len(DataHandler.dutch_voc_list):
                raise Exception("Error: The docx file contains less rows than the json file. Please add the missing rows to the docx file or delete the json file to create a new one.")

        print("Vocabulary loaded successfully!")

    # save dutch_voc_list, german_voc_list, phonetics_list to a json file
    def save_data_json():
        with open('vocabulary_data.json', 'w') as file:
            json.dump([ DataHandler.dutch_voc_list, 
                        DataHandler.german_voc_list, 
                        DataHandler.phonetics_list,
                        DataHandler.asked,
                        DataHandler.correct,
                        DataHandler.wrong,
                        DataHandler.points,
                        DataHandler.last_asked,
                        DataHandler.current_date]
                       , file)
            # alternative: json.dump(DataHandler.data_frame, file)

    # load dutch_voc_list, german_voc_list, phonetics_list from a json file
    def load_data_json():
        with open('vocabulary_data.json', 'r') as file:
            loaded_data_frame = json.load(file)
            DataHandler.dutch_voc_list = loaded_data_frame[0]
            DataHandler.german_voc_list = loaded_data_frame[1]
            DataHandler.phonetics_list = loaded_data_frame[2]
            DataHandler.asked = loaded_data_frame[3]
            DataHandler.correct = loaded_data_frame[4]
            DataHandler.wrong = loaded_data_frame[5]
            DataHandler.points = loaded_data_frame[6]
            DataHandler.last_asked = loaded_data_frame[7]
            DataHandler.current_date = loaded_data_frame[8]

            # create empty lists for asked, correct, wrong, points, last_asked, if they don't exist yet
            nr_of_vocs = len(DataHandler.dutch_voc_list)
            if len(DataHandler.asked) == 0:
                DataHandler.asked = [0] * nr_of_vocs
            if len(DataHandler.correct) == 0:
                DataHandler.correct = [0] * nr_of_vocs
            if len(DataHandler.wrong) == 0:
                DataHandler.wrong = [0] * nr_of_vocs
            if len(DataHandler.points) == 0:
                for i in range(nr_of_vocs):
                    DataHandler.points.append([])
            if len(DataHandler.last_asked) == 0:
                for i in range(nr_of_vocs):
                    DataHandler.last_asked.append("never")

            return loaded_data_frame

    # print complete vocabulary list to console
    def print_complete_voc_list():
        for i in range(len(DataHandler.dutch_voc_list)):
            print(DataHandler.dutch_voc_list[i], " :: ", DataHandler.german_voc_list[i])
            print("")

# class to handle the user interface with pyqt
class UserInterface:
    def __init__(self):
        self.app = QApplication([])
        self.window = QMainWindow()
        self.main_menu()

    # ramp up the main menu
    def main_menu(self):
        # Create a central widget and set it as the main widget for the window
        central_widget = QWidget()
        self.window.setCentralWidget(central_widget)
        # change background color
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)  # Center horizontally
        
        # Create buttons with adjusted size and font size
        button_width = 250
        button_height = 60  # Adjust height if needed
        font_size = 16  # Adjust font size as needed
        
        self.start_training_button = QPushButton('Start Training')
        self.start_training_button.setFixedSize(button_width, button_height)
        self.start_training_button.setFont(QFont("Arial", font_size))
        
        self.explore_statistics_button = QPushButton('Explore Statistics')
        self.explore_statistics_button.setFixedSize(button_width, button_height)
        self.explore_statistics_button.setFont(QFont("Arial", font_size))
        
        self.refresh_vocabulary_button = QPushButton('Refresh Vocabulary List')
        self.refresh_vocabulary_button.setFixedSize(button_width, button_height)
        self.refresh_vocabulary_button.setFont(QFont("Arial", font_size))
        
        # Add buttons to layout
        layout.addWidget(self.start_training_button)
        layout.addWidget(self.explore_statistics_button)
        layout.addWidget(self.refresh_vocabulary_button)
        
        # Set the layout for the central widget
        central_widget.setLayout(layout)
        
        # Connect button clicks to their respective functions
        self.start_training_button.clicked.connect(self.select_training_type)
        self.explore_statistics_button.clicked.connect(self.explore_statistics)
        self.refresh_vocabulary_button.clicked.connect(self.refresh_vocabulary)
        
        # Set the window properties
        self.window.setWindowTitle('Vocabulary App')
        self.window.showMaximized()  # Open in fullscreen mode

    # train vocabs after pressing the button in the main menu
    def select_training_type(self):
        
        # SET UP THE LAYOUT
        # three buttons, one for Dutch -> German, one for German -> Dutch, Random; they launch the respective functions

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        
        # button dutch -> german
        button_dutch_german = QPushButton('Dutch -> German')
        button_dutch_german.setFixedSize(500, 60) # width, height
        button_dutch_german.setFont(QFont("Arial", 16))
        layout.addWidget(button_dutch_german)

        # button german -> dutch
        button_german_dutch = QPushButton('German -> Dutch')
        button_german_dutch.setFixedSize(500, 60) # width, height
        button_german_dutch.setFont(QFont("Arial", 16))
        layout.addWidget(button_german_dutch)

        # button random
        button_random = QPushButton('Random')
        button_random.setFixedSize(500, 60) # width, height
        button_random.setFont(QFont("Arial", 16))
        layout.addWidget(button_random)

        # refresh the window
        self.window.update()

        # Connect button clicks to their respective functions
        button_dutch_german.clicked.connect(self.start_dutch_german)
        button_german_dutch.clicked.connect(self.start_german_dutch)
        button_random.clicked.connect(self.start_random)

    # go back to main menu
    def end_training(self):
        UserInterface.main_menu(self)

    # show dutch vocab and ask for german translation
    def start_dutch_german(self):
        # boolean to check if a slider was already added
        slider_added = False

        # show translation of the word; make slider visible
        def show_translation():
            nonlocal label_text
            nonlocal slider_added
            if label_text == ProgramLogic.short_lines(dutch_word)+"\n"+phonetics:
                label_text = ProgramLogic.short_lines(correct_translation)
            else:
                label_text = ProgramLogic.short_lines(dutch_word)+"\n"+phonetics
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
            DataHandler.asked[vocab_nr] += 1
            # add date to last_asked
            DataHandler.last_asked[vocab_nr] = DataHandler.current_date[-1]
            # add current points to list of all points
            DataHandler.points[vocab_nr].append(self.slider.value())
            # add +1 to correct or wrong
            if self.slider.value() > 60:
                DataHandler.correct[vocab_nr] += 1
            elif self.slider.value() < 40:
                DataHandler.wrong[vocab_nr] += 1

            # save statistics
            DataHandler.save_data_json()
            # ask for a new vocab
            UserInterface.start_dutch_german(self)

        # SET UP THE LAYOUT

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Create a QLabel with vocabulary to ask
        dutch_word, correct_translation, phonetics, vocab_nr = ProgramLogic.ask_question()

        # ToDo: if phenetics is empty, don't show it
        label_text = ProgramLogic.short_lines(dutch_word)+"\n"+phonetics
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

    # show german vocab and ask for dutch translation
    def start_german_dutch(self):
                # boolean to check if a slider was already added
        slider_added = False

        # show translation of the word; make slider visible
        def show_translation():
            nonlocal label_text
            nonlocal slider_added
            if label_text == ProgramLogic.short_lines(dutch_word)+"\n"+phonetics:
                label_text = ProgramLogic.short_lines(german_word)
            else:
                label_text = ProgramLogic.short_lines(dutch_word)+"\n"+phonetics
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
            DataHandler.asked[vocab_nr] += 1
            # add date to last_asked
            DataHandler.last_asked[vocab_nr] = DataHandler.current_date[-1]
            # add current points to list of all points
            DataHandler.points[vocab_nr].append(self.slider.value())
            # add +1 to correct or wrong
            if self.slider.value() > 60:
                DataHandler.correct[vocab_nr] += 1
            elif self.slider.value() < 40:
                DataHandler.wrong[vocab_nr] += 1

            # save statistics
            DataHandler.save_data_json()
            # ask for a new vocab
            UserInterface.start_german_dutch(self)

        # SET UP THE LAYOUT

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Create a QLabel with vocabulary to ask
        dutch_word, correct_translation, phonetics, vocab_nr = ProgramLogic.ask_question()
        german_word = correct_translation

        # ToDo: if phenetics is empty, don't show it
        label_text = ProgramLogic.short_lines(german_word)
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

    # randomly ask for a dutch or german word
    def start_random(self):
        # boolean to check if a slider was already added
        slider_added = False

        # show translation of the word; make slider visible
        def show_translation():
            nonlocal label_text
            nonlocal slider_added
            if label_text == ProgramLogic.short_lines(dutch_word)+"\n"+phonetics:
                label_text = ProgramLogic.short_lines(correct_translation)
            else:
                label_text = ProgramLogic.short_lines(dutch_word)+"\n"+phonetics
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
            DataHandler.asked[vocab_nr] += 1
            # add date to last_asked
            DataHandler.last_asked[vocab_nr] = DataHandler.current_date[-1]
            # add current points to list of all points
            DataHandler.points[vocab_nr].append(self.slider.value())
            # add +1 to correct or wrong
            if self.slider.value() > 60:
                DataHandler.correct[vocab_nr] += 1
            elif self.slider.value() < 40:
                DataHandler.wrong[vocab_nr] += 1

            # save statistics
            DataHandler.save_data_json()
            # ask for a new vocab
            UserInterface.start_random(self)

        # SET UP THE LAYOUT

        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Create a QLabel with vocabulary to ask
        dutch_word, correct_translation, phonetics, vocab_nr = ProgramLogic.ask_question()

        # ToDo: if phenetics is empty, don't show it
        if random.randint(0,1) == 0:
            label_text = ProgramLogic.short_lines(dutch_word)+"\n"+phonetics
        else:
            label_text = ProgramLogic.short_lines(correct_translation)
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

    # show statistics in a table after pressing the button in the main menu	
    def explore_statistics(self):

        def back_to_main_menu():
            UserInterface.main_menu(self)
        
        # Remove existing widgets from the layout
        layout = self.window.centralWidget().layout()
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # transform all data into a table form
        table_data = ProgramLogic.create_statistics_data()

        # Create a pyqt table with that data
        table = QTableView()
        model = TableModel(table_data)
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

    # load vocabulary from docx file within the application via button in the main menu
    def refresh_vocabulary(self):
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
            DataHandler.load_docx('DUTCH.docx')
            DataHandler.save_data_json()
        except:
            print("\n\nError: \nNo vocabulary data found as docx. Please add a docx file with the name 'DUTCH.docx' to the same folder as this program.\nThe docx file should contain a table with three columns: Dutch, German and Phonetics. No headings or other columns are allowed.\n\n")

        # go back to main menu
        UserInterface.main_menu(self)

    # initialize the ui
    def run(self):
        sys.exit(self.app.exec())

# rather complex functions that are used in the program, outsourced to a separate class for better overview
class ProgramLogic:
    # choose a vocab based on how often voc was asked, how correct it was answered, how long ago it was asked 
    def choose_vocab(show_console_text = True):
        # based on given statistics, choose a vocab to ask next
        # important is: how often was it asked, how correct (with how many slider points) was it answered, how long ago was it asked... we make a score for these three and order the vocabs by that scores
        # when several items have the same score in a sublist, shuffle them randomly (otherwise they always get orderd by index and it gets boring)
        # never ask the same item twice in a row (in fact an asked voc gets blocked for ten iterations)

        # shuffle a list when several items have the same score in a sublist
        def shuffle_list(list_to_shuffle):
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
        
        # sort vocabs by when they were last asked
        def create_sublist_last_asked():
            list_last_asked = [] # list that sorts the vocabs by when they were last asked
            for i in range(len(DataHandler.last_asked)):
                # if the word was never asked, then add the date 01/01/2000 to the list
                if DataHandler.last_asked[i] == "never":
                    list_last_asked.append(["01/01/2000", i])
                else:
                    list_last_asked.append([DataHandler.last_asked[i], i])
            list_last_asked.sort(reverse=False)

            # shuffle the list make it a bit more random
            list_last_asked = shuffle_list(list_last_asked)
            if show_console_text: print("\nlist last asked: \n",list_last_asked)
            return list_last_asked
        
        # sort vocabs by how often they were asked
        def create_sublist_asked_often():
            list_asked_often = [] # list that sorts the vocabs by how often it was asked
            for i in range(len(DataHandler.asked)):
                list_asked_often.append([DataHandler.asked[i], i])
            list_asked_often.sort(reverse=False)

            # shuffle the list make it a bit more random
            list_asked_often = shuffle_list(list_asked_often)
            if show_console_text: print("\nlist asked often: \n",list_asked_often)
            return list_asked_often
        
        # sort vocabs by how many points they got in the last 10 times they were asked
        def create_sublist_average_points():
            list_average_points = [] # list that sorts the vocabs by how many points they got in the last 10 times they were asked
            for i in range(len(DataHandler.points)):
                if len(DataHandler.points[i]) > 10:
                    list_average_points.append([sum(DataHandler.points[i][-10:])/10, i])
                elif len(DataHandler.points[i]) > 0:
                    list_average_points.append([sum(DataHandler.points[i])/len(DataHandler.points[i]), i])
                else:
                    list_average_points.append([0, i])
            list_average_points.sort(reverse=False)

            # shuffle the list make it a bit more random
            list_average_points = shuffle_list(list_average_points)
            if show_console_text: print("\nlist average points: \n",list_average_points)
            return list_average_points
        
        # create a list with a final score of each vocab
        def create_total_list():
            # when you are the last vocab in a certain list, you get 1 point, second last 2 points, third last 3 points, etc.
            # the score of all three lists gets combined in list_total_score
            list_total_score = []
            # give weights to the three lists
            weight_last_asked = 1
            weight_asked_often = 1
            weight_average_points = 2

            for i in range(len(DataHandler.dutch_voc_list)):
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
            if show_console_text: print("\nTen last session vocabs (blocked for taken as next vocab): ", DataHandler.session_vocabs[-10:])
            if list_total_score[i][1] not in DataHandler.session_vocabs[-10:]:
                chosen_vocab = list_total_score[i][1]
                if show_console_text: print("\nlist total score: \n",list_total_score)
                if show_console_text: print("\nNext vocab to ask: ", DataHandler.dutch_voc_list[chosen_vocab], " with score ", list_total_score[i][0])
                break

        # save the selection in the session_vocabs
        DataHandler.session_vocabs.append(chosen_vocab)
  
        # return the chosen vocab nr
        return chosen_vocab

    # get the right data for the question
    def ask_question():
        global vocab_nr
        vocab_nr = ProgramLogic.choose_vocab()
        # alternatively random vocab selection:
        #vocab_nr = random.randint(0, len(DataHandler.data_frame[0])-1)
        dutch_word = DataHandler.data_frame[0][vocab_nr]
        correct_translation = DataHandler.data_frame[1][vocab_nr]
        phonetics = DataHandler.data_frame[2][vocab_nr]

        return dutch_word, correct_translation, phonetics, vocab_nr
    
    # if the text is too long, divide it into several lines
    def short_lines(text):
        words = text.split()  # Split the input text into words
        lines = []  # List to store the lines

        current_line = ""  # Initialize an empty line
        for word in words:
            # Check if adding the word to the current line exceeds the 30 character limit
            if len(current_line) + len(word) + 1 <= 30:
                if current_line == "":
                    current_line = word
                else:
                    current_line += " " + word
            else:
                lines.append(current_line)  # Add the current line to the list of lines
                current_line = word  # Start a new line with the current word
        
        # Add the last line (if any) to the list of lines
        if current_line:
            lines.append(current_line)

        # Join the lines with newline characters to get the final output
        text_output = "\n".join(lines)
        
        return text_output

    # create statistical data that will be shown in a table under "Explore Statistics"
    def create_statistics_data():
        data_list = []

        # create a list that tells how many points the vocs have on average
        average_points = []
        for i in range(len(DataHandler.points)):
            if len(DataHandler.points[i]) > 0:
                average_points.append(round(sum(DataHandler.points[i])/len(DataHandler.points[i]), 2))
            else:
                average_points.append(0)
        # create a list that tell how many points the vocs have on average in the last 10 times they were asked
        average_points_last_10 = []
        for i in range(len(DataHandler.points)):
            if len(DataHandler.points[i]) > 10:
                average_points_last_10.append(round(sum(DataHandler.points[i][-10:])/10, 2))
            elif len(DataHandler.points[i]) > 0:
                average_points_last_10.append(round(sum(DataHandler.points[i])/len(DataHandler.points[i]), 2))
            else:
                average_points_last_10.append(0)

        for i in range(len(DataHandler.dutch_voc_list)):
            data_list.append([
                DataHandler.dutch_voc_list[i], 
                DataHandler.german_voc_list[i], 
                DataHandler.phonetics_list[i], 
                DataHandler.asked[i], 
                DataHandler.correct[i], 
                DataHandler.wrong[i], 
                DataHandler.points[i],
                average_points[i],
                average_points_last_10[i], 
                DataHandler.last_asked[i]
            ])

        table_data = pd.DataFrame(data_list, columns=['Dutch', 'German', 'Phonetics', 'Asked', 'Correct', 'Wrong', 'Points', 'Average Points', 'Average Points Last 10', 'Last Asked'])

        return table_data

def main():
    # try to load vocabulary from json file, if it doesn't exist, then load it from docx file
    try:
        DataHandler.data_frame = DataHandler.load_data_json()
    except:
        try:
            DataHandler.load_docx('DUTCH.docx')
        except:
            print("\n\nError: \nNo vocabulary data found as json or docx. Please add a docx file with the name 'DUTCH.docx' to the same folder as this program.\nThe docx file should contain a table with three columns: Dutch, German and Phonetics. No headings or other columns are allowed.\nThe program will now exit.\n\n")
            sys.exit()

    # add todays date to current_date
    date = datetime.date.today()
    DataHandler.current_date.append(date.strftime("%d/%m/%Y"))

    # Run the application
    ui = UserInterface()
    ui.run()

if __name__ == "__main__":
    main()