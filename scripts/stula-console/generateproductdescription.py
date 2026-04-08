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
        
        category_upper = product['category'].upper()

        # Prompt for short description translation
        prompt_short = (
            f"Translate the following short description to {lang_name}. Ensure the translation is accurate and maintains the sales-driven tone:\n\n"
            f"{product['short_description_en']}\n"
            "Make sure to use appropriate terminology and phrasing that resonates with native speakers of the language."
        )

        # Prompt for long description translation
        prompt_long = (
            f"Translate the following long description to {lang_name}. Ensure the translation is comprehensive and captures the nuances of the original text:\n\n"
            f"{product['description_en']}\n"
            "Use native expressions and maintain the engaging, sales-driven tone throughout the description."
        )

        product[short_description_key] = translate_text(prompt_short)
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
            temperature=0.2
        )
        translation = response.choices[0].message.content
        return translation
    except Exception as e:
        print(f"Error translating text: {e}")
        return ""

def generate_short_description(product, previous_descriptions):
    category_upper = product['category'].upper()
    product_ref = f"{category_upper} {product['title']}"
    
    # Include only the last 2 previous descriptions
    recent_descriptions = "\n".join(previous_descriptions[-2:])

    prompt = (
       f"Product: {product_ref}\n"
        f"Format: {product['format']}\n"
        f"Flavor: {product['flavor']}\n"
        f"Nicotine: {product['nicotine']} mg\n"
        "\n"
        "Write a short description for the product, consisting of 2-4 sentences max about the product. "
        "Ensure each sentence introduces new information about the product. "
        "Avoid repeating phrases or sentences from the previous descriptions. "
        "Highlight the product's flavor and conclude with a compelling, sales-driven sentence. "
    )

    try:
        while True:
            response = openai.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                messages=[
                    {"role": "system", "content": "Act as a creative product description writer specializing in nicotine pouches."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=356,
                temperature=0
            )

            description = response.choices[0].message.content
            print(f"Generated short description: {description}")

            user_input = input("Accept this description? (a = accept, d = decline): ")
            if user_input.lower() == 'a':
                return description

    except Exception as e:
        print(f"Error generating short description for {product['title']}: {e}")
        return ""

def generate_long_description(product, previous_descriptions):
    category_upper = product['category'].upper()
    product_ref = f"{category_upper} {product['title']}"
    
    # Include only the last 2 previous descriptions
    recent_descriptions = "\n".join(previous_descriptions[-2:])
    
    # Define parts of the long description
    parts = [
        "Introduce the product briefly in 1-2 sentences. Ensure these sentences do not repeat previous introductions and are concise. Only introduce it in 1-2 sentences, do not write about it.",
        "Describe the flavor of the product in 1-2 sentences. Use simple, formal language and avoid repeating flavor descriptions. Be straightforward and avoid overly descriptive or story-like language.",
        "Discuss the convenience of use and discreet fit in 1-2 sentences. Ensure these sentences are unique and add new information.  Be straightforward and avoid overly descriptive or story-like language.",
        "Explain the nicotine content and recommend it for beginners or experienced users based on the content in 1-3 sentences. Avoid repetition. Be straightforward and avoid overly descriptive or story-like language.",
        "Conclude with a strong sales-driven sentence in 1-2 sentences. Ensure this conclusion is unique.  Be straightforward and avoid overly descriptive or story-like language."
    ]

    description = ""    
    
    for i, part in enumerate(parts):
        while True:
            prompt = (
                f"Product: {product_ref}\n"
                f"Format: {product['format']}\n"
                f"Flavor: {product['flavor']}\n"
                f"Nicotine: {product['nicotine']} mg\n"
                f"{'Existing description: ' + description if i > 0 else ''}\n"
                f"{part}\n"
                "Ensure this paragraph fits nicely with the existing content and does not repeat any information already provided. "
                "Write in a way that is easy for beginner to intermediate English speakers to understand. "
                "Focus specifically on the aspect described in the current part. "
                "Avoid using labels like 'Example:'. Ensure all sentences are complete and the description is well-structured. "
            )

            try:
                response = openai.chat.completions.create(
                    model="gpt-4-1106-preview",
                    messages=[
                        {"role": "system", "content": "Act as a creative product description writer specializing in nicotine pouches."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=356,
                    temperature=0
                )

                paragraph = response.choices[0].message.content
                print(f"Generated paragraph: {paragraph}")

                user_input = input("Accept this paragraph? (a = accept, d = decline): ")
                if user_input.lower() == 'a':
                    description += " " + paragraph
                    break  # Break the inner while loop and proceed to the next part

            except Exception as e:
                print(f"Error generating long description paragraph for {product['title']}: {e}")
                return ""
    
    return description.strip()

def main():
    # Load the JSON data from the input file
    with open('proizvodi.json', 'r', encoding='utf-8') as file:
        products = json.load(file)

    previous_short_descriptions = []
    previous_long_descriptions = []

    # Iterate over each product and generate descriptions
    for product in products:
        print(f"\nGenerating descriptions for: {product['title']}\n")
        
        # Check if short description already exists
        if 'short_description_en' in product and product['short_description_en']:
            print(f"Skipping short description generation for {product['title']}, already exists.")
            short_description = product['short_description_en']
        else:
            short_description = generate_short_description(product, previous_short_descriptions)
            product['short_description_en'] = short_description
            previous_short_descriptions.append(short_description)
        
        # Check if long description already exists
        if 'description_en' in product and product['description_en']:
            print(f"Skipping long description generation for {product['title']}, already exists.")
            long_description = product['description_en']
        else:
            long_description = generate_long_description(product, previous_long_descriptions)
            product['description_en'] = long_description
            previous_long_descriptions.append(long_description)

        # Check if translations already exist
        languages = ['de', 'it', 'fr', 'hu', 'tr', 'sr-latn']
        translations_needed = False
        for lang in languages:
            short_description_key = f'short_description_{lang}'
            description_key = f'description_{lang}'
            if short_description_key not in product or not product[short_description_key]:
                translations_needed = True
                break
            if description_key not in product or not product[description_key]:
                translations_needed = True
                break
        
        if translations_needed:
            product = translate_descriptions(product)
        else:
            print(f"Skipping translation for {product['title']}, all translations already exist.")

        # Print the translated descriptions for debugging
        print(f"Translated descriptions for {product['title']}:")
        for lang in languages:
            short_key = f'short_description_{lang}'
            long_key = f'description_{lang}'
            print(f"{lang}: {product.get(short_key, '')}")
            print(f"{lang}: {product.get(long_key, '')}")

        # Print the generated descriptions for debugging
        print(f"Short description for {product['title']}: {short_description}")
        print(f"Long description for {product['title']}: {long_description}")
        
        # Save the updated data after each product
        with open('proizvodi.json', 'w', encoding='utf-8') as file:
            json.dump(products, file, indent=4, ensure_ascii=False)

if __name__ == '__main__':
    main()
