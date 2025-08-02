# TODO

OPEN ISSUES

- Two checks in main method must be sourced out to own functions, these function must spawn a visible gui message before closing the program because later there will be no console output
- Add AI modus for German->Dutch (currently only Dutch->German is implemented, even if you click the button for German->Dutch)
- more buttons to go back, abort, close the program, etc
- when there is no voc data in the beginning, the program has to ask which languages the user wants to translate from and to
- the languages throughout the program must be based on the languages in the xlsx file, currently they are hardcoded to Dutch and German
- better visuals in the UI
    - better layout
    - add the background image from the files folder to the main page
- Check the calculation of the row width, sometimes the letters are cut off (especially in German)


DONE

- display proper error messages when no voc data or no openai api key is found
- create new xlsx when neither json nor xlsx file is found
- Shift json file and xlsx file to the file folder
- fix "Refresh Vocabulary List" button, since it does not seem to work properly


