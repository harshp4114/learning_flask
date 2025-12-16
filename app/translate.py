from flask_babel import _
from app import app
from googletrans import Translator

def translate(text,source_language,dest_language):
    translator=Translator()
    translated=translator.translate(text,src=source_language,dest=dest_language)
    t=translated.text
    return t