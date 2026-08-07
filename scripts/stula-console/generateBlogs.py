import os
import openai
import json
import random
import re

openai.api_key = os.environ.get("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("Postavi environment varijablu OPENAI_API_KEY (npr. u .env).")
existing_data = []

# List of target languages and their respective codes
languages = ['de', 'it', 'fr', 'hu', 'tr', 'sr-latn']

def translate_text(text, target_language):
    prompt = f"Translate the following text to {target_language}:\n{text}"
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Translate text accurately and appropriately."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.5
        )
        translation = response.choices[0].message.content
        return translation
    except Exception as e:
        print(f"Error translating text: {e}")
        return text  # Return the original text if translation fails

def update_links(text, language_code):
    updated_text = re.sub(
        r'https://www.snuswe.com/en-us/',
        f'https://www.snuswe.com/{language_code}/',
        text
    )
    return updated_text

def translate_blog_content(blog_content):
    translations = {}

    for lang in languages:
        main_title = translate_text(blog_content['main_title'], lang)
        main_title = update_links(main_title, lang)
        
        subtitles = [translate_text(subtitle, lang) for subtitle in blog_content['subtitles']]
        subtitles = [update_links(subtitle, lang) for subtitle in subtitles]
        
        paragraphs = [translate_text(paragraph, lang) for paragraph in blog_content['paragraphs']]
        paragraphs = [update_links(paragraph, lang) for paragraph in paragraphs]

        translations[f'main_title_{lang}'] = main_title
        translations[f'subtitles_{lang}'] = subtitles
        translations[f'paragraphs_{lang}'] = paragraphs
    
    return translations

# Load JSON data
with open('kategorije.json', encoding='utf-8') as f:
    categories = json.load(f)
with open('proizvodi.json', encoding='utf-8') as f:
    products = json.load(f)
with open('blogovi.json', encoding='utf-8') as f:
    blogs = json.load(f)
    existing_data.extend(blogs)  # Ensure existing data is correctly appended

def generate_main_title(theme):
    prompt = (
        f"Theme: {theme}\n"
        "Generate an engaging main title for a blog based on the provided theme. Only talk positively about the product."
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Act as a creative title writer for blogs related to nicotine pouches."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.5
        )
        main_title = response.choices[0].message.content
        return main_title
    except Exception as e:
        print(f"Error generating main title: {e}")
        return ""

def generate_subtitle(blog_title, previous_subtitles):
    prompt = (
        f"Blog Title: {blog_title}\n"
        f"Existing Subtitles: {', '.join(previous_subtitles)}\n"
        "Generate an engaging subtitle for the blog that fits well with the provided title and existing subtitles. Avoid repetition and ensure each subtitle covers a different aspect."
        "Dont put the prefixes Subtitle: or any other"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Act as a creative subtitle writer for blogs related to nicotine pouches."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0.7
        )
        subtitle = response.choices[0].message.content
        return subtitle
    except Exception as e:
        print(f"Error generating subtitle: {e}")
        return ""
    
def format_blog_title_for_url(title):
    # Replace special characters with nothing
    cleaned_title = re.sub(r'[^a-zA-Z0-9\s]', '', title)
    # Replace spaces with hyphens
    formatted_title = cleaned_title.replace(' ', '-')
    return formatted_title.lower()


def generate_paragraph(subtitle, previous_paragraphs, insert_blog_link=False):
    elements = ["bullets", "statistics", None]  # Remove quotes from the options to reduce frequency
    selected_elements = random.sample(elements, k=random.randint(0, 2))
    
    elements_text = ""
    if "bullets" in selected_elements:
        elements_text += " Include bullet points formatted with <ul> and <li> tags."
    if "statistics" in selected_elements:
        elements_text += " Include statistics."

    # Randomly decide to include a product or category (with reduced frequency)
    include_products = random.random() < 0.35
    include_categories = random.random() < 0.35

    product_mentions = []
    if include_products:
        mention_products = random.choices(products, k=random.randint(0, 2))  # Limit to fewer products
        for product in mention_products:
            product_title = product['title']
            product_category = product['category']
            product_final = f"{product_category} {product_title}"
            product_mentions.append(f"<a href='https://www.snuswe.com/en-us/{product_final.lower().replace(' ', '-')}'>{product_final}</a>")

    category_mentions = []
    if include_categories:
        mention_categories = random.choices(categories, k=random.randint(0, 2))  # Limit to fewer categories
        for category in mention_categories:
            category_name = category['name']
            category_mentions.append(f"<a href='https://www.snuswe.com/en-us/nicotine-pouches/{category_name.lower().replace(' ', '-')}'>{category_name}</a>")

    prompt = (
        f"Subtitle: {subtitle}\n"
        f"Existing Paragraphs: {''.join(previous_paragraphs)}\n"
        f"Generate a comprehensive paragraph for the subtitle. {elements_text} "
        f"Integrate the following into the text: {', '.join(product_mentions)} {', '.join(category_mentions)}. "
        f"Avoid repetition and ensure the paragraph is informative. Only talk positively about the product."
        "Dont put the prefixes Subtitle: or any other"
        "Make sure u finish all the sentences or and thoughts"
    )

    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Act as a creative paragraph writer for blogs related to nicotine pouches."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.5
        )
        paragraph = response.choices[0].message.content
        # Insert a link to another blog in one of the paragraphs
        if insert_blog_link:
            blog = random.choice(blogs)
            blog_title = blog['main_title']
            formatted_blog_title = format_blog_title_for_url(blog_title)
            blog_link = f"https://www.snuswe.com/en-us/{formatted_blog_title}"
            paragraph = re.sub(
                r'\b(?:in|about|related to|more details)\b',
                f'<a href="{blog_link}">Read more about this topic</a>',
                paragraph,
                1  # Only replace the first occurrence
            )
            insert_blog_link = False  # Ensure blog link is only inserted once

        
        return paragraph
    except Exception as e:
        print(f"Error generating paragraph: {e}")
        return ""

def determine_number_of_subtitles(theme):
    prompt = (
        f"Theme: {theme}\n"
        "Based on this theme, how many unique and engaging subtitles can be generated without repeating information? Provide a number between 4 and 7."
        "Only Generate a number no text"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Generate a number of subtitles for blogs."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=50,
            temperature=0.5
        )
        number_of_subtitles = int(response.choices[0].message.content)
        return min(max(number_of_subtitles, 4), 7)  # Ensure the number is between 4 and 7
    except Exception as e:
        print(f"Error determining the number of subtitles: {e}")
        return 4

def main():
    theme = input("Enter the theme for the blog: ")

    # Generate main title
    while True:
        main_title = generate_main_title(theme)
        print(f"Generated main title: {main_title}")
        user_input = input("Accept this main title? (a = accept, d = decline): ")
        if user_input.lower() == 'a':
            break

    # Determine the number of subtitles
    num_subtitles = determine_number_of_subtitles(theme)

    subtitles = []
    paragraphs = []

    blog_link_inserted = False

    # Generate subtitles
    for i in range(num_subtitles):
        while True:
            subtitle = generate_subtitle(main_title, subtitles)
            print(f"Generated subtitle: {subtitle}")
            user_input = input("Accept this subtitle? (a = accept, d = decline): ")
            if user_input.lower() == 'a':
                subtitles.append(subtitle)
                break

    # Generate paragraphs for each subtitle
    for subtitle in subtitles:
        while True:
            insert_blog_link = not blog_link_inserted and random.random() < 0.5
            paragraph = generate_paragraph(subtitle, paragraphs, insert_blog_link=insert_blog_link)
            print(f"Generated paragraph: {paragraph}")
            user_input = input("Accept this paragraph? (a = accept, d = decline): ")
            if user_input.lower() == 'a':
                paragraphs.append(paragraph)
                if insert_blog_link:
                    blog_link_inserted = True
                break

    # Combine everything into a single blog content
    blog_content = {
        "main_title": main_title,
        "subtitles": subtitles,
        "paragraphs": paragraphs
    }

    # Translate blog content
    translations = translate_blog_content(blog_content)
    blog_content.update(translations)

    # Generate the new blog ID
    if existing_data:
        last_id = max(item['id'] for item in existing_data)
    else:
        last_id = 0
    blog_content['id'] = last_id + 1

    existing_data.append(blog_content)

    # Save to a JSON file
    with open('blogovi.json', 'w', encoding='utf-8') as file:
        json.dump(existing_data, file, indent=4, ensure_ascii=False)

    print("Blog content generated and saved to blogovi.json")

if __name__ == '__main__':
    main()
