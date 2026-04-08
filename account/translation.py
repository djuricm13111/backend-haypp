from enum import Enum
from django.utils.translation import gettext_lazy as _
from modeltranslation.translator import register, TranslationOptions
from .models import Blog

@register(Blog)
class BlogTranslationOptions(TranslationOptions):
    fields = ('title','subtitles','paragraphs')