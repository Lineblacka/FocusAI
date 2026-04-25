# FocusAI Service

FocusAI Service is a FastAPI + React chat product built for Bulgarian productivity coaching. This release is cleaned up for GitHub publishing with a stronger UI, safer backend defaults, session-isolated memory, Docker support, and test coverage around prompt and security behavior.

## Highlights

- Professional React/Vite chat UI with responsive sidebar and richer product presentation
- Rewritten Bulgarian system prompt with cleaner tone and fewer instruction leaks
- Session-isolated conversation history instead of one shared message pool
- Security hardening with request size limits, rate limiting, trusted hosts, and response security headers
- Dockerized deployment plus static frontend serving from FastAPI
- Pytest coverage for health, prompt wiring, session isolation, and quality filtering

## Project Structure

```text
app/          FastAPI app, prompt, schemas, CLI
api/          REST routes and middleware
services/     AI, intent, command and quality logic
config/       environment settings
storage/      JSON persistence
frontend/     Vite React source
static/       built frontend served by FastAPI
tests/        API and unit tests
```

## Local Setup

1. Copy the environment file:

```bash
copy .env.example .env
```

2. Set your OpenRouter key in `.env`:

```env
OPENROUTER_API_KEY=your_real_key
```

3. Install backend dependencies:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
uvicorn app.main:app --reload
```

5. Open:

```text
http://127.0.0.1:8000
```

## Frontend Development

```bash
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173`.

To build the production frontend into `static/`:

```bash
cd frontend
npm run build
```

## Docker

```bash
docker compose up --build
```

Open `http://127.0.0.1:8000`.

## API Examples

Health:

```bash
curl http://127.0.0.1:8000/health
```

Chat:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Кой си ти\",\"session_id\":\"default\"}"
```

Streaming chat:

```bash
curl -N -X POST http://127.0.0.1:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Дай ми план за дисциплина\",\"session_id\":\"default\"}"
```

## CLI

```bash
python main.py
```

## Tests

```bash
pytest
```

## Environment Notes

`OPENROUTER_MODELS` accepts a comma-separated fallback list.

Example:

```env
OPENROUTER_MODELS=openai/gpt-oss-20b:free,nvidia/nemotron-3-nano-30b-a3b:free
```

Persistent data is stored in `DATA_DIR/memory.json`.
