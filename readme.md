# DungeonMasterBot

DungeonMasterBot is a voice-first, two-player one-shot harness. OpenAI Realtime performs the spoken Dungeon Master, while a separate authoritative game ledger tracks characters, physical dice, public campaign state, private facts, NPC motives, and reveal gates.

The first playable story is **The Bell Beneath Briar Glen**, an original rain-soaked mystery designed for roughly 45 minutes. The model performs the story; it does not own the canonical state or get unrestricted access to secrets.

## Vertical slice

- Bidirectional browser voice over WebRTC using `gpt-realtime-2.1`.
- Server-minted short-lived Realtime credentials; the long-lived OpenAI key never reaches React.
- An adapter boundary for the announced GPT-Live model when its API becomes available.
- Two live, versioned character sheets with sourced armor math, attacks, movement, proficiencies, features, traits, HP, death saves, spell slots, class resources, currency, and enriched inventory.
- A complete spellcasting view that distinguishes known, prepared, always-prepared, and spellbook spells while showing spell source, save DC, attack bonus, focus, components, range, duration, rituals, and concentration.
- Guided two-player setup using SRD 5.2.1 level-3 Champion Fighter and Evoker Wizard pregens or a strictly allowlisted local JSON character file.
- Physical d20 workflow: the DM requests a roll, the players roll real dice, and the UI accepts only the natural face.
- SQLite state with optimistic versions and idempotent mutations.
- A secrecy-safe Director runtime: performer context excludes unrevealed truths, hidden DCs, raw motives, private state, and future scenes; bounded tools persist scene changes, discoveries, and NPC reactions.
- An original generated Dungeon Master portrait whose jaw, aura, and speech meter react to live output audio.

## Architecture

```text
Microphone <-> OpenAI Realtime WebRTC <-> voice performer
                      | function calls
                      v
              guarded browser executor
                      |
                      v
Flask API -> authoritative SQLite ledger -> public character sheets
    |
    +-> private campaign Director -> secrecy-safe performer projection
```

The Realtime session exposes eleven least-privilege intents: read public state, read the safe performer projection, request a physical roll, apply damage, apply healing, award currency, use or restore a character resource, advance the campaign, record a generic discovery, and record a generic NPC reaction. The application supplies state versions and idempotency keys; the engine supplies character modifiers and maps generic story events to private reveal gates. Model-authored tool arguments cannot provide a DC, modifier, fact ID, future scene, motive, or state version.

## Requirements

- Python 3.11+
- Node.js 18+ and npm 9+
- An OpenAI API key with Realtime access
- `uv` 0.9+ (or pip and a virtual environment)

## Configure

Create an ignored `.env` file in the repository root:

```dotenv
OPENAI_API_KEY=sk-...

# Optional overrides
OPENAI_REALTIME_MODEL=gpt-realtime-2.1
OPENAI_REALTIME_VOICE=marin
OPENAI_REALTIME_REASONING_EFFORT=low
FRONTEND_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

The legacy text/RAG variables are needed only if you deliberately call the old `/chat` endpoint. Importing the Flask app no longer initializes those network-backed resources.

## Run locally

From the repository root, install dependencies if needed:

```bash
uv sync
npm install --prefix frontend/chatbot-frontend
```

Start the API and frontend in separate terminals:

```bash
uv run python -m bot.api.server
```

```bash
npm run dev --prefix frontend/chatbot-frontend
```

Open [http://localhost:3000](http://localhost:3000), then choose **Begin voice adventure**. The browser will request microphone permission. A ready-made two-character party is loaded for the smoke-test path; choose **Create or import your party** to run the setup flow.

## Verify

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -v
CI=true npm test --prefix frontend/chatbot-frontend -- --runInBand --watchAll=false
npm run build --prefix frontend/chatbot-frontend
```

## Rules, characters, and campaign imports

The local rules baseline is the official SRD 5.2.1 under `rules/srd/`, with its required Creative Commons attribution in `rules/srd/ATTRIBUTION.md`. Characters and campaigns declare a ruleset ID so older and newer D&D mechanics cannot be mixed silently. The separation between redistributable rules, authoritative game state, and future private campaign packages is documented in `rules/README.md`.

D&D Beyond does not currently offer this project a supported public API for a user's purchased-book entitlements or characters. This harness therefore does not scrape or automate D&D Beyond. The current setup accepts a local, user-selected JSON character file and strips unknown/private fields before the server validates it. A future official provider can be added behind the import boundary without changing the game ledger.

A future import of a lawfully obtained adventure should remain a private source package with provenance and visibility labels. It must not copy campaign prose into the public SRD catalog or expose unrevealed DM material to the voice performer.

## Key locations

- `bot/api/server.py` — Flask app factory and voice-safe session instructions
- `bot/api/realtime_routes.py` — ephemeral Realtime credential broker and tool schemas
- `bot/game/` — validated authoritative state and SQLite store
- `bot/director/` — immutable campaign loader, reveal gates, and safe projections
- `campaigns/the_bell_beneath_briar_glen.json` — canonical one-shot
- `frontend/chatbot-frontend/src/voice/` — WebRTC provider and voice controller
- `frontend/chatbot-frontend/src/character/` — setup and live sheets
- `frontend/chatbot-frontend/src/avatar/` — animated portrait component
