from flask import Flask, request, render_template, url_for, redirect
import requests
import re
import os
from llama_index.core import SimpleDirectoryReader
from together import Together

app = Flask(__name__)

TASTY_API_KEY = '922aa2818dmsh87a963db48df974p1c9419jsndcd5a62b76d5'
TASTY_API_HOST = 'tasty.p.rapidapi.com'
TASTY_API_URL = 'https://tasty.p.rapidapi.com/recipes/list'

client = Together(api_key='b744993071b5d9c4e2da8dd2efb993621f349608cb57c3761f7c723ef365d2ae')

def extract_ingredients_with_llama3(user_query):
    response = client.chat.completions.create(
        model="meta-llama/Llama-3-8b-chat-hf",
        messages=[
            {"role": "system", "content": "generate a list of recipes in a paragraph format where each recipe name is followed by a space. No comma or anything else. Only write the name of the recipe and nothing else. The main ingredients of the recipe will be provided by the user. Do not write anything extra."},
            {"role": "user", "content": user_query}
        ],
    )
    processed_query = response.choices[0].message.content
    print(processed_query)
    ingredients = re.findall(r'\b\w+\b', processed_query.lower())
    return ingredients, processed_query

def get_recipes(ingredients):
    querystring = {"q": ','.join(ingredients), "from": "0", "size": "20"}
    headers = {
        "x-rapidapi-key": TASTY_API_KEY,
        "x-rapidapi-host": TASTY_API_HOST
    }
    response = requests.get(TASTY_API_URL, headers=headers, params=querystring)
    return response.json()

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def clear_recipe_directory(directory='recipes'):
    if os.path.exists(directory):
        for file in os.listdir(directory):
            file_path = os.path.join(directory, file)
            if os.path.isfile(file_path):
                os.unlink(file_path)

def save_recipes_to_text_files(recipes, directory='recipes'):
    if not os.path.exists(directory):
        os.makedirs(directory)

    for recipe in recipes:
        file_name = sanitize_filename(f"{recipe['name'].replace(' ', '_')}.txt")
        file_path = os.path.join(directory, file_name)
        
        with open(file_path, 'w', encoding='utf-8') as file:
            file.write(f"Name: {recipe['name']}\n")
            file.write(f"Description: {recipe['description']}\n")
            if 'thumbnail_url' in recipe:
                file.write(f"Image URL: {recipe['thumbnail_url']}\n")
            if 'original_video_url' in recipe:
                file.write(f"Video URL: {recipe['original_video_url']}\n")
            if 'thumbnail_alt_text' in recipe:
                file.write(f"Image Alt Text: {recipe['thumbnail_alt_text']}\n")
            if 'prep_time_minutes' in recipe:
                file.write(f"Prep Time Minutes: {recipe['prep_time_minutes']}\n")
            if 'yields' in recipe:
                file.write(f"Yields: {recipe['yields']}\n")
            if 'nutrition' in recipe and 'calories' in recipe['nutrition']:
                file.write(f"Calories: {recipe['nutrition']['calories']}\n")
            if 'instructions' in recipe:
                for j, instruction in enumerate(recipe['instructions'], 1):
                    file.write(f"Instruction {j}: {instruction['display_text']}\n")

def read_recipes_from_directory(directory='recipes'):
    reader = SimpleDirectoryReader(directory)
    documents = reader.load_data()
    return documents

def parse_recipe_docs(documents):
    recipes = []
    for doc in documents:
        content = doc.text.split('\n')
        recipe = {}
        instructions = []
        reading_instructions = False
        
        for line in content:
            line = line.strip()
            
            if line.startswith('Instruction '):
                # Collect instructions
                instructions.append(line.split(': ', 1)[1])
                reading_instructions = True
            elif line == '':
                # End of instructions section
                reading_instructions = False
            else:
                if reading_instructions:
                    instructions.append(line)
                else:
                    if line.startswith('Name:'):
                        recipe['name'] = line[len('Name: '):]
                    elif line.startswith('Description:'):
                        recipe['description'] = line[len('Description: '):]
                    elif line.startswith('Image URL:'):
                        recipe['thumbnail_url'] = line[len('Image URL: '):]
                    elif line.startswith('Thumbnail Text:'):
                        recipe['thumbnail_alt_text'] = line[len('Thumbnail Text: '):]
                    elif line.startswith('Video URL:'):
                        recipe['original_video_url'] = line[len('Video URL: '):]
                    elif line.startswith('Prep Time Minutes:'):
                        recipe['prep_time_minutes'] = line[len('Prep Time Minutes: '):]
                    elif line.startswith('Yields:'):
                        recipe['yields'] = line[len('Yields: '):]
                    elif line.startswith('Calories:'):
                        recipe['calories'] = line[len('Calories: '):]
        
        if instructions:
            recipe['instructions'] = '\n'.join(instructions)
        
        if recipe:
            recipes.append(recipe)
    
    return recipes




@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_recipes', methods=['POST'])
def recipes():
    user_query = request.form.get('query')
    ingredients, processed_query = extract_ingredients_with_llama3(user_query)
    recipes_data = get_recipes(ingredients)
    save_recipes_to_text_files(recipes_data['results'])
    recipe_docs = read_recipes_from_directory()
    formatted_recipes = parse_recipe_docs(recipe_docs)
    
    return render_template('recipes.html', recipes=formatted_recipes, llama_response=processed_query)

@app.route('/recipe_detail', methods=['POST'])
def recipe_detail():
    recipe = request.form.to_dict()
    return render_template('recipe_detail.html', recipe=recipe)

if __name__ == '__main__':
    app.run(debug=True)

