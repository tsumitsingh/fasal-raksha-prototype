# Fasal Raksha

Fasal Raksha is split into two independently deployable services:

- **Frontend:** the Vite-built static app in `dist/`.
- **Backend:** the FastAPI service in `backend/`, with Supabase for auth, Postgres, and private image storage.

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

The frontend defaults to `http://localhost:8000`. Set `VITE_API_URL` in the root `.env` when the API is hosted elsewhere.

## Production deployment

The repository includes [render.yaml](render.yaml) for the backend and [vercel.json](vercel.json) for the frontend. The recommended free deployment flow is:

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint**, select the repository, and apply `render.yaml`.
3. Add the backend secrets in Render. Set `FRONTEND_ORIGINS` to the final Vercel origin, for example `https://fasalraksha.vercel.app`.
4. In Vercel, import the same repository. Set `VITE_API_URL` to the public Render API URL, for example `https://fasalraksha-api.onrender.com`.
5. Run the Supabase schema before testing registration or scans.

Do not commit `.env`, `backend/.env`, service-role keys, or API tokens. GitHub, Render, and Vercel environment variables are the correct place for secrets and deployment URLs.

### Frontend

Build and serve the static output from any static hosting provider:

```powershell
npm ci
npm run build
```

Set `VITE_API_URL` to the public HTTPS URL of the backend before building. The included root `Dockerfile` serves the result with Nginx; pass the value as a build argument:

```powershell
docker build --build-arg VITE_API_URL=https://api.example.com -t fasalraksha-frontend .
```

### Backend

The included `backend/Dockerfile` runs Uvicorn on `0.0.0.0` and respects the platform `PORT` variable:

```powershell
docker build -f backend/Dockerfile -t fasalraksha-backend backend
```

Configure these backend environment variables in the hosting provider's secret manager. Never commit them:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `HF_TOKEN`
- `TAVILY_API_KEY`
- `HF_VISION_MODEL` and `HF_CHAT_MODEL` (optional overrides)
- `SUPABASE_STORAGE_BUCKET` (normally `crop-images`)
- `FRONTEND_ORIGINS` as a comma-separated list containing the deployed frontend HTTPS origin

Run `backend/supabase_schema.sql` once in the Supabase SQL editor before accepting traffic. Verify `https://api.example.com/health` reports `database_schema_ready: true`.

Images are uploaded to the private Supabase Storage bucket and only written to temporary container storage while the AI model processes them. Do not attach a persistent local upload directory to the API as application state.

## Health and checks

```powershell
npm run build
python -m compileall -q backend/app
```
>>>>>>> 1db5d0a (Prepare separate frontend and backend deployment)
