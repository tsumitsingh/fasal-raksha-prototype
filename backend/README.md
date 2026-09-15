# Fasal Raksha AI backend

## Setup

From the `backend` directory:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Add these values to `.env`:

- `HF_TOKEN` and `TAVILY_API_KEY` for disease guidance.
- `SUPABASE_URL` from Supabase Project Settings > API.
- `SUPABASE_SERVICE_ROLE_KEY` from Supabase Project Settings > API. Keep this only in the backend `.env`; never put it in browser JavaScript.

The model names can be changed there without changing Python code.

## Supabase setup

1. Create a Supabase project.
2. Phone Auth and Twilio are not required. The backend creates confirmed password accounts through the Supabase service-role API.
3. Open SQL Editor, open [`supabase_schema.sql`](supabase_schema.sql), select the entire file, and run it as one query. This creates the `scans` table, farmer profiles, unique phone protection, row-level security policies, and the private `crop-images` Storage bucket. Do not run only the `ALTER TABLE` lines.
4. Restart FastAPI and open `http://localhost:8000/health`. `supabase_configured` must be `true` and `otp_enabled` must be `false`.

The app uses Supabase Auth for mobile/password login, Postgres for scan history, and private Storage for crop photos. The backend creates short-lived signed image URLs after checking the logged-in user's bearer token.

Registration does not send OTPs. It asks only for full name, Indian mobile number, and password. The mobile number is stored in `farmer_profiles` with a unique index, so a second registration with the same number is rejected.

## Run

```powershell
uvicorn app.main:app --reload --port 8000
```

The frontend expects the API at `http://localhost:8000`. Start the frontend from the project root with `npm run dev` or another static server.

## API flow

- `POST /api/scans`: accepts an image as the `image` multipart field, detects a likely disease, searches Tavily, and creates a scan session.
- `GET /api/scans/{scan_id}`: loads the image, finding, answer, and sources for the chat page.
- `POST /api/scans/{scan_id}/chat`: accepts `{ "question": "..." }` and returns a source-backed LangChain answer.
- `GET /health`: reports whether Hugging Face and Tavily keys are configured.

The dashboard opens the live rear camera first. `Upload Image Instead` remains available as the secondary path. Both paths open the assistant window after the authenticated scan is saved.
