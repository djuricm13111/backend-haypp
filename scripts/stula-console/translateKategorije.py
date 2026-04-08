import os
import openai
import json

openai.api_key = os.environ.get("OPENAI_API_KEY", "")
if not openai.api_key:
    raise RuntimeError("Postavi environment varijablu OPENAI_API_KEY (npr. u .env).")

def translate_descriptions(product):
    languages = {
        'de': 'German',
        'it': 'Italian',
        'fr': 'French',
        'hu': 'Hungarian',
        'tr': 'Turkish',
        'sr-latn': 'Serbian (Latin)'
    }

    for lang_code, lang_name in languages.items():
        short_description_key = f'short_description_{lang_code}'
        description_key = f'description_{lang_code}'

        # Check if translations already exist
        if short_description_key in product and product[short_description_key]:
            print(f"Skipping short description translation to {lang_name} for {product['name']}, already exists.")
        else:
            # Prompt for short description translation
            prompt_short = (
                f"Translate the following short description to {lang_name}. Ensure the translation is accurate and maintains the sales-driven tone:\n\n"
                f"{product['short_description_en']}\n"
                "Make sure to use appropriate terminology and phrasing that resonates with native speakers of the language."
            )
            product[short_description_key] = translate_text(prompt_short)

        if description_key in product and product[description_key]:
            print(f"Skipping long description translation to {lang_name} for {product['name']}, already exists.")
        else:
            # Prompt for long description translation
            prompt_long = (
                f"Translate the following long description to {lang_name}. Ensure the translation is comprehensive and captures the nuances of the original text:\n\n"
                f"{product['description_en']}\n"
                "Use native expressions and maintain the engaging, sales-driven tone throughout the description."
            )
            product[description_key] = translate_text(prompt_long)

    return product

def translate_text(prompt):
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            messages=[
                {"role": "system", "content": "You are a professional translator specializing in product descriptions."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=1000,
            temperature=0.7
        )
        translation = response.choices[0].message.content
        return translation
    except Exception as e:
        print(f"Error translating text: {e}")
        return ""

def main():
    # Load the JSON data from the input file
    with open('kategorije.json', 'r', encoding='utf-8') as file:
        products = json.load(file)

    # Iterate over each product and translate descriptions
    for product in products:
        print(f"\nTranslating descriptions for: {product['name']}\n")
        
        # Translate descriptions if needed
        product = translate_descriptions(product)

        # Print the translated descriptions for debugging
        languages = ['de', 'it', 'fr', 'hu', 'tr', 'sr-latn']
        for lang in languages:
            short_key = f'short_description_{lang}'
            long_key = f'description_{lang}'
            print(f"{lang}: {product.get(short_key, '')}")
            print(f"{lang}: {product.get(long_key, '')}")

        # Save the updated data after each product
        with open('kategorije.json', 'w', encoding='utf-8') as file:
            json.dump(products, file, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()
