import json


# Separate basic and SEO data
with open(f'products.json', 'r') as file:  # Zamenite 'path_to_your_json_file.json' sa stvarnom putanjom
    products_data = json.load(file)

basic_data = []

seo_data = []



for item in products_data:

    # Basic data

    basic_item = {

        "id": item["id"],

        "title": item["title"],

        "category": item["category"],

        "nicotine": item["nicotine"],

        "pouches_per_can": item["pouches_per_can"],

        "format": item["format"],

        "flavor": item["flavor"],

        "net_weight": item["net_weight"],

        "manufacturer": item["manufacturer"],

        "images": item["images"],

    }

    basic_data.append(basic_item)



    # SEO data

    seo_item = {

        "id": item["id"],
        **{key: value for key, value in item.items() if key.startswith("short_description_")},
        **{key: value for key, value in item.items() if key.startswith("description_")},

    }

    seo_data.append(seo_item)



# Write data to JSON files

with open("basic_data.json", "w", encoding="utf-8") as basic_file:

    json.dump(basic_data, basic_file, indent=4, ensure_ascii=False)



with open("seo.json", "w", encoding="utf-8") as seo_file:

    json.dump(seo_data, seo_file, indent=4, ensure_ascii=False)



"Files created: basic_data.json and seo_data.json"