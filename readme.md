# DungeonMasterBot

DungeonMasterBot is an experiment in running a Dungeons & Dragons experience with the help of large language models. A Flask API handles the DM logic, while a modern React interface delivers the chat experience with quality-of-life features such as auto-scroll anchoring.

## Project Layout

- `bot/` – Python code for the Dungeon Master brain, including the Flask API (`bot/api/server.py`), conversation logic, and LangChain helpers.
- `frontend/chatbot-frontend/` – React client served with Create React App.
- `requirements.txt` / `pyproject.toml` – Python dependency definitions (use whichever workflow you prefer).

## Requirements

- Python 3.11+
- Node.js 18+ and npm 9+
- An OpenAI API key and access to a supported chat/completions model
- Optionally: Poetry if you prefer it over `pip`

## Environment Variables

Create a `.env` file at the repository root with at least the following values:

```
OPENAI_API_KEY=sk-...
GPT_MODEL=gpt-3.5-turbo
RULESET_FILEPATH=/absolute/path/to/rules.pdf
EMBEDDINGS_CHUNK_SIZE=1000            # optional; defaults vary by LangChain version
```

Additional values referenced in the code (such as paths for saved characters) can be customised to your filesystem.

## Setup & Running

All commands below assume you are in the repository root.

### 1. Backend (Flask API)

Install dependencies (pick one workflow):

```bash
# Using Poetry
poetry install

# or using pip
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Start the API server:

```bash
# Poetry
poetry run python bot/api/server.py

# pip / virtualenv
python bot/api/server.py
```

The service listens on `http://localhost:8000/chat`.

### 2. Frontend (React UI)

Install dependencies and start the dev server without leaving the repo root:

```bash
npm install --prefix frontend/chatbot-frontend
npm run dev --prefix frontend/chatbot-frontend
```

The UI runs at [http://localhost:3000](http://localhost:3000) and sends chat requests to the Flask API at port 8000.

### 3. Development Tips

- Keep the backend and frontend running in separate terminals.
- Adjust the axios endpoint in `frontend/chatbot-frontend/src/App.js` if you expose the API on a different host or port.
- Ensure a `logs/` directory exists (`mkdir logs`) so the backend can write `logs/debug.log` for troubleshooting.

## Next Steps

- Populate the FAISS index under `dbs/documentation/faiss_index` to enable rulebook retrieval.
- Extend the function-calling capabilities in `bot/utils/functions.py` for richer gameplay.
