# Running TAARS Locally

This guide starts the TAARS backend, profile dashboard, and embeddable widget test page.

## Prerequisites

- Docker Desktop with Docker Compose
- Node.js and npm
- Python 3.11 or newer

Run all commands from the repository root unless a step says otherwise.

## First-Time Setup

Create the environment file:

```bash
cp .env.example .env
```

Set the portfolio owner in `.env`:

```dotenv
OWNER_NAME=Amrut
OWNER_CONTACT_EMAIL=you@example.com
```

An LLM key is optional for manual profile testing. Resume import requires a configured provider; without one, grounded visitor answers still use an extractive fallback.

```dotenv
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your-key
```

Install the frontend dependencies:

```bash
npm install
```

For a local Python environment outside Docker:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 1. Start the Backend

The recommended setup runs FastAPI, PostgreSQL with pgvector, and Valkey through Docker Compose:

```bash
docker compose up --build api
```

Compose starts the `postgres` and `valkey` dependencies automatically. Keep this terminal open.

Backend URLs:

- API: <http://localhost:8000>
- Health check: <http://localhost:8000/health>
- API documentation: <http://localhost:8000/docs>

To run the Python API directly while keeping its dependencies in Docker:

```bash
docker compose up -d postgres valkey
.venv/bin/uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

The `.env` database URL must use `localhost` for this direct-Python option:

```dotenv
DATABASE_URL=postgresql+asyncpg://taars:taars@localhost:5432/taars
VALKEY_URL=redis://localhost:6379
```

## 2. Start the Dashboard

Open another terminal at the repository root:

```bash
npm run frontend:dev
```

Open the dashboard at <http://localhost:5173>.

The dashboard development server proxies `/api` requests to `http://localhost:8000`.

### Prepare Data for the Widget

The widget answers from an indexed published profile, not from the mutable draft.

1. Open **Profile** in the dashboard.
2. Add at least one experience or project.
3. Complete the required dates and content.
4. Select **Save draft**.
5. Select **Publish** to create a candidate profile version.
6. Open **Indexing**.
7. Select **Index and activate**.
8. Optionally ask a question on the Indexing screen to confirm retrieval.

After changing profile information, save and publish again, then index and activate the new candidate. The previous active version remains available until activation succeeds.

### Import a Resume

1. Open **Profile builder**.
2. Select **Choose resume** and upload a PDF or DOCX file.
3. Review the records added to Experiences, Projects, Skills, Education, Certifications, and Achievements.
4. Confirm the complete resume descriptions were preserved, review every generated outcome, then complete any missing dates.
5. Select **Save draft** when the imported profile is correct.

Import does not save or publish automatically. Existing matching records keep owner-written values; missing values are filled from the import and list fields are merged.

## 3. Build and Run the Widget Test Page

Build the self-contained widget bundle:

```bash
npm run widget:build
```

Serve the widget directory from another terminal:

```bash
cd widget
../.venv/bin/python -m http.server 5174
```

Open <http://localhost:5174/test.html>.

The page loads `widget/dist/widget.iife.js` and sends chat requests to `http://localhost:8000`, as configured in `widget/test.html`.

To return to the repository root:

```bash
cd ..
```

## What to Verify

1. The chat button appears in the bottom-right corner.
2. Opening it shows the AI assistant identity and message input.
3. A question related to the published profile receives an answer.
4. Supported answers display a **Grounded** label.
5. Expanding **source** or **sources** shows the supporting profile records.
6. An unrelated question returns an insufficient-information response with **No profile evidence**.
7. Unpublished draft changes do not appear in answers.
8. Private projects and unapproved personal topics do not appear in evidence.

## Stopping the Services

Stop the dashboard, widget server, or direct Python API with `Ctrl+C` in their terminals.

Stop the Docker services with:

```bash
docker compose down
```

To stop containers without removing them:

```bash
docker compose stop
```

## Common Problems

### Port Already in Use

Check whether another TAARS or Docker process already uses ports `8000`, `5173`, or `5174`. Stop that process before starting the corresponding service.

### Widget Returns a Generic Error

Confirm that:

- `http://localhost:8000/health` responds successfully.
- A profile has been published.
- The current published version has been indexed.
- The API terminal does not show a database error.

### Answer Uses Older Profile Information

Open the dashboard's **Indexing** view. Activate a waiting candidate or re-index the active profile.

### Natural LLM Answer Is Not Generated

Check `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY` in `.env`, then restart the backend. Without a valid key, TAARS intentionally uses the local extractive answer fallback.
