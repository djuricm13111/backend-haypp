import json
from django.contrib.auth.models import User
from account.models import Blog  # Zamenite 'account' sa stvarnim imenom vaše aplikacije
#exec (open('scripts/data/import_blogs.py').read())

# Putanja do JSON fajla
with open('scripts/data/blogs.json', 'r') as file:
    blogs_data = json.load(file)


for blog_data in blogs_data:
    if isinstance(blog_data, dict):

        blog = Blog(
            title=blog_data.get('main_title', ''),
            subtitles=blog_data.get('subtitles', []),
            paragraphs=blog_data.get('paragraphs', []),
        )
    for lang_code in ['de', 'it', 'fr', 'hu', 'tr', 'sr_latn']:  # List of language codes for which you have translations
        title_key = f'title_{lang_code}'
        main_title_key = f'main_title_{lang_code}'
        if main_title_key in blog_data:
            setattr(blog, title_key, blog_data[main_title_key])

        subtitles_key = f'subtitles_{lang_code}'
        if subtitles_key in blog_data:
            setattr(blog, subtitles_key, blog_data[subtitles_key])
        paragraphs_key = f'paragraphs_{lang_code}'
        if paragraphs_key in blog_data:
            setattr(blog, paragraphs_key, blog_data[paragraphs_key])
    try:
        blog.save()
        print(f"Blog '{blog.title}' has been saved.")
    except Exception as e:
        print(f"Error saving blog '{blog_data.get('main_title', 'Unknown Title')}': {e}")
