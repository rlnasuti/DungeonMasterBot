# What is DungeonMasterBot?

DungeonMasterBot is a program powered by ChatGPT to act as a Dungeon Master! It demonstrates various GPT related concepts including Knowledge Retrieval from PDFs and GPT's 'function calling' capabilities. This is a work in progress. It's driven by my desire to play D&D even when there is no one around to be dungeonmaster as well as my love of experimentation with LLMs. It will be iteratively built upon.

I expect that I will only update this readme after significant updates, so it may not be up to date on what functionality is available.

The first commit provides only minimal functionality - it can create a character and save it locally. The bot can work with the player to create a character, or you can request it make one for you. It's also pretty good at making characters based on fictional characters from novels or movies.

Future planned functionality will give it the ability to update character state. Then I'll likely work to make a combat simulator. The ultimate goal is to provide this bot a digital campaign and for the bot to be able to run it from start to finish through multiple sessions.

# Setup

Run both the Flask app and the React frontend:
Flask: python your_flask_file.py
React: cd chatbot-frontend && npm start