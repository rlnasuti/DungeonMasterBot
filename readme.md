# What is DungeonMasterBot?

This is a work in progress. It's driven by my desire to play D&D even when there is no one around to be dungeonmaster. It will be iteratively built upon.

I expect that I will only update this readme after significant updates, so it may not be up to date on what functionality is available.

The first commit provides only minimal functionality - it can create a character and save it locally. The bot can work with the player to create a character, or you can request it make one for you. It's also pretty good at making characters based on fictional characters from novels or movies.

Future planned functionality will give it the ability to update character state. Then I'll likely work to make a combat simulator. The ultimate goal is to provide this bot a digital campaign and for the bot to be able to run it from start to finish through multiple sessions.

# Setup

You'll need to do some setup on your local to get this running. I've tried to make this simple, but one can never account for strange local issues. I use venv to manage virtual environments and so the instructions below are using venv, but if you want to use a different virtual environment manager go right ahead. I used python 3.10 to create this

1. Create a new virtual environment to run this program
`python3.10 -m venv venv`
2. Activate new virtual environment
`source venv/bin/activate`
3. Install dependencies from requirements.txt
`pip install -r requirements.txt`
4. Create a directory called "sourcebooks" in the root of this repo 
5. Place any PDF's you have of D&D sourcebooks inside it
6. Create a file called .env in the root of this repo
7. Populate .env with the following variables:
```
OPENAI_API_KEY = <your openai API key>
RULESET_FILEPATH = <absolute path of the directory where you stored pdf sourcebooks>
GPT_MODEL = <this must be either gpt-3.5-turbo-0613 or gpt-4-0613 or a larger context version of one of these models>
EMBEDDINGS_CHUNK_SIZE = 4 (this will likely be moved out of the .env file, but for now just do this)
```
8. Run indexer.py (Future update will likely remove the need for this step)
9. Run app.py
10. ...
11. Profit

# Contact

WOTC if you see this and are interested then let's talk. I can be reached at `robert.nasuti@gmail.com`