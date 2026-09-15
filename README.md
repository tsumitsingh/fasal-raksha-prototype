# Fasal Raksha

Fasal Raksha is a full-stack FastAPI application. The production container builds the Vite frontend and serves its pages and API from one Render web service. Supabase provides authentication, Postgres, and private image storage.

## Local development

1. Install frontend dependencies and start Vite:

	```powershell
	npm ci
	npm run dev
	```

2. Configure the backend:

	```powershell
	Copy-Item backend/.env.example backend/.env
	```

	Fill in the Supabase, Hugging Face, and Tavily values in `backend/.env`.

3. Start the API from `backend`:

	```powershell
	uvicorn app.main:app --reload --port 8000
	```

The frontend uses the same origin as the API when `VITE_API_URL` is not set. For separate local frontend development, set `VITE_API_URL=http://localhost:8000`.

## Production deployment

The repository includes [render.yaml](render.yaml) and [Dockerfile.render](Dockerfile.render) for one combined service:

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint**, select the repository, and apply `render.yaml`.
3. Add the secrets listed below in Render. Set `FRONTEND_ORIGINS` to the Render service URL, for example `https://fasalraksha-fullstack.onrender.com`.
4. Run the Supabase schema before testing registration or scans.

Do not commit `.env`, `backend/.env`, service-role keys, or API tokens. GitHub, Render, and Vercel environment variables are the correct place for secrets and deployment URLs.

### Render full-stack service

Render builds the frontend and backend from the root Dockerfile:

```powershell
npm ci
npm run build
```

The service serves the frontend at `/` and the API at `/api/...`. No frontend API URL is required for this same-origin setup.

Configure these Render environment variables:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `HF_TOKEN`
- `TAVILY_API_KEY`
- `HF_VISION_MODEL` and `HF_CHAT_MODEL` (optional overrides)
- `SUPABASE_STORAGE_BUCKET` (normally `crop-images`)
- `FRONTEND_ORIGINS` containing the deployed Render HTTPS origin

Run `backend/supabase_schema.sql` once in the Supabase SQL editor. Verify `https://your-service.onrender.com/health` reports `database_schema_ready: true`.

Images are uploaded to the private Supabase Storage bucket and only written to temporary container storage while the AI model processes them. Do not attach a persistent local upload directory to the API as application state.

## Health and checks

```powershell
npm run build
python -m compileall -q backend/app
```
