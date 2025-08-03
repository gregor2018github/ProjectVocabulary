"""
Description:

This program is a vocabulary trainer for Dutch and German words. It loads the vocabulary from a VOCABS.xlsx file and saves the statistics in a vocabulary_data.json file.
The user interface is created with pyqt6. Key feature is a slider to evaluate how well the translation was known (right=good, left=bad). The statistics are visualized in a table.
Vocabulary training is possible in both directions (Dutch->German and vice versa). 
The program chooses the next word based on how often it was asked, how correct it was answered and how long ago it was asked.
The program also never asks the same word twice in a session of 10 words.
The program can start with a json file or with a xlsx file. If there is no json file, then the xlsx file is loaded and a json file is created.
The vocabulary can constantly be enlarged by adding new words to the end of the xlsx file. Also translations can be changed. The order of rows must not be changed though.
The main menu has a button to refresh the vocabulary list from the xlsx file while keeping the statistics from the json file.

Recently added features: 

An AI training modus was added to the program, where a given training word will result in randomly generated sentences. 
Furthermore, the program is upgraded with text-to-speech (TTS) capabilities to read out the example sentences.
Both features are based on the OpenAI API, which requires an API key to be saved as the environment variable OPENAI_API_KEY.

"""