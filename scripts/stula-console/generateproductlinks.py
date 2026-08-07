import json
import re
from datetime import datetime

# Function to format blog titles for URL
def format_blog_title_for_url(title):
    # Replace special characters with nothing
    cleaned_title = re.sub(r'[^a-zA-Z0-9\s]', '', title)
    # Replace spaces with hyphens
    formatted_title = cleaned_title.replace(' ', '-')
    return formatted_title.lower()

# Function to generate URLs and check for duplicates
def generate_urls(data, categories, blogs, base_url, languages, additional_pages):
    existing_urls = set()
    
    # Load existing URLs from the sitemap file if it exists
    try:
        with open('sitemap.xml', 'r', encoding='utf-8') as file:
            for line in file:
                if "<loc>" in line:
                    url = line.strip().replace("<loc>", "").replace("</loc>", "")
                    existing_urls.add(url)
    except FileNotFoundError:
        # If the file does not exist, proceed without error
        pass

    # Get the current date in ISO 8601 format
    current_date = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S+00:00')

    # Open the sitemap file in append mode
    with open('sitemap.xml', 'a', encoding='utf-8') as file:
        # Generate URLs for product data
        for lang in languages:
            for item in data:
                # Convert title to lowercase and replace spaces with dashes
                category_and_title = f"/{item['category']}-{item['title']}".lower().replace(' ', '-')
                # Concatenate full URL
                full_url = f"{base_url}/{lang}{category_and_title}"
                
                # Check if the URL already exists in the file
                if full_url not in existing_urls:
                    # Write to file in XML format
                    file.write(f'\t<url>\n\t\t<loc>{full_url}</loc>\n\t\t<lastmod>{current_date}</lastmod>\n\t</url>\n')
                    # Add the URL to the existing URLs set
                    existing_urls.add(full_url)

        # Generate URLs for additional pages
        for lang in languages:
            for page in additional_pages:
                # Concatenate full URL
                full_url = f"{base_url}/{lang}/{page}"
                
                # Check if the URL already exists in the file
                if full_url not in existing_urls:
                    # Write to file in XML format
                    file.write(f'\t<url>\n\t\t<loc>{full_url}</loc>\n\t\t<lastmod>{current_date}</lastmod>\n\t</url>\n')
                    # Add the URL to the existing URLs set
                    existing_urls.add(full_url)

        # Generate URLs for categories
        for lang in languages:
            for category in categories:
                # Convert category name to lowercase and replace spaces with dashes
                category_name = category['name'].lower().replace(' ', '-')
                # Concatenate full URL
                full_url = f"{base_url}/{lang}/nicotine-pouches/{category_name}"
                
                # Check if the URL already exists in the file
                if full_url not in existing_urls:
                    # Write to file in XML format
                    file.write(f'\t<url>\n\t\t<loc>{full_url}</loc>\n\t\t<lastmod>{current_date}</lastmod>\n\t</url>\n')
                    # Add the URL to the existing URLs set
                    existing_urls.add(full_url)

        # Generate URLs for blogs
        for lang in languages:
            for blog in blogs:
                # Format blog title for URL
                blog_title = format_blog_title_for_url(blog['main_title'])
                # Concatenate full URL
                full_url = f"{base_url}/{lang}/blogs/{blog_title}"
                
                # Check if the URL already exists in the file
                if full_url not in existing_urls:
                    # Write to file in XML format
                    file.write(f'\t<url>\n\t\t<loc>{full_url}</loc>\n\t\t<lastmod>{current_date}</lastmod>\n\t</url>\n')
                    # Add the URL to the existing URLs set
                    existing_urls.add(full_url)

# Load JSON files
try:
    # Open the products JSON file
    with open('proizvodi.json', 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Open the categories JSON file
    with open('kategorije.json', 'r', encoding='utf-8') as file:
        categories = json.load(file)

    # Open the blogs JSON file
    with open('blogovi.json', 'r', encoding='utf-8') as file:
        blogs = json.load(file)

    # Base URL parts
    base_url = "https://www.snuswe.com"

    # Language codes
    languages = ["sr-latn", "de", "it", "en-us", "fr", "hu", "tr"]

    # Additional pages
    additional_pages = [
        "nicotine-pouches",
        "new-arrivals",
        "best-sellers",
        "cart",
        "support",
        "blogs",

    ]

    # Generate and write URLs to the sitemap file
    generate_urls(data, categories, blogs, base_url, languages, additional_pages)

except Exception as e:
    print(f"An error occurred: {e}")
