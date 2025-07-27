import gdown

url = 'https://docs.google.com/document/d/1bgBBAao4y3PnTlm8Aq7y8sqSen-ZrNdgb47kgM5rdc8'
output = 'test'
gdown.download(url, output, quiet=False, format = 'docx', fuzzy=True)