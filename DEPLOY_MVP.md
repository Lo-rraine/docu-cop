# Document Copilot: 1-Hour MVP Deployment to Railway

This guide gets the app live on Railway in ~30-60 minutes.

## Prerequisites

- ✅ Railway account (free tier OK): https://railway.app
- ✅ GitHub account (repo connected to Railway)
- ✅ Supabase database ready (get DATABASE_URL from Supabase dashboard)
- ✅ OpenAI API key (from https://platform.openai.com/api-keys)
- ✅ All secrets: Supabase keys, JWT secret, OpenAI key

## Step 1: Prepare Secrets (2 min)

Generate a JWT secret:
```bash
openssl rand -hex 32
# Output: abc123def456... (copy this)
```

Get your secrets from:
- **Supabase**: Dashboard → Settings → API (copy SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY)
- **Database URL**: Dashboard → Settings → Database → Connection string (copy and URL-encode the password)
- **OpenAI**: https://platform.openai.com/api-keys (copy your API key)

## Step 2: Create Railway Project (5 min)

1. Go to https://railway.app/dashboard
2. Click "New Project"
3. Click "Deploy from GitHub"
4. Authorize Railway to access GitHub (if needed)
5. Search for your repo (`document-copilot`)
6. Click "Deploy Now"

**Note:** Railway will attempt to auto-detect. If it fails, continue to Step 3 anyway — we'll configure it manually.

## Step 3: Configure Backend Service (5 min)

In Railway dashboard:

1. **Important:** Click "Settings" on the service (top-right)
2. Under "Builder", select "Dockerfile"
3. Set "Dockerfile Path" to `backend/Dockerfile`
4. Set "Root Directory" to `backend` (if available)
5. Go to "Environment" tab
6. Add these variables (paste your actual values):

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
JWT_SECRET=<your-generated-secret-from-step-1>
DATABASE_URL=postgresql://postgres.cydxygyuaamvjindwmci:fKFUOaL8v4uAiLnl@aws-0-eu-west-1.pooler.supabase.com:5432/postgres
DATABASE_PASSWORD=fKFUOaL8v4uAiLnl
OPENAI_API_KEY=sk-proj-your-key
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
ALLOWED_ORIGINS=http://localhost:5173,https://<your-frontend-domain>.up.railway.app
ENVIRONMENT=production
```

4. Go to "Deploy" → "Deployment Triggers"
5. Set "Watch Paths" to `backend/**` (only redeploy on backend changes)
6. Click "Redeploy"

**Wait for deployment to finish (~3-5 min)**

## Step 4: Configure Frontend Service (5 min)

1. Go back to Railway project dashboard
2. Click "+ New" button
3. Select "GitHub Repo"
4. Select your repo again (for frontend)
5. In the new service, click "Settings" (top-right)
6. Under "Builder", select "Dockerfile"
7. Set "Dockerfile Path" to `frontend/Dockerfile`
8. Set "Root Directory" to `frontend`
9. Go to "Environment" tab and add:

```
VITE_API_BASE_URL=https://<your-backend-url>.up.railway.app
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-anon-key
```

   **To get your backend URL:**
   - In Railway, go to the backend service
   - Click "Generate Domain" (top-right) if not already done
   - Copy the URL from "Public URL" section

10. After adding env vars, click "Redeploy"
11. Wait for deployment to finish (~3-5 min)

**Wait for deployment to finish (~3-5 min)**

## Step 5: Verify Deployment (5 min)

### Backend Health Check

1. In Railway, find your backend service
2. Click "View Logs"
3. Look for: `Uvicorn running on http://0.0.0.0:8000`
4. In a new tab, visit: `https://<your-backend-service>.up.railway.app/health`
5. You should see: `{"status": "ok"}`

If you see errors:
- Check DATABASE_URL is correct (copy again from Supabase)
- Check OPENAI_API_KEY is valid
- Check JWT_SECRET is set

### Frontend Verification

1. In Railway, find your frontend service
2. Click on the service name to open it
3. You should see the login page

If you see a blank page or errors:
- Check VITE_API_BASE_URL matches your backend URL
- Check browser console (F12) for errors
- Check Railway logs for build errors

## Step 6: Test End-to-End (5 min)

1. Open frontend: `https://<your-frontend-service>.up.railway.app`
2. Register with email + password
3. Create a new chat
4. Type a question (e.g., "What's Nvidia?")
5. Wait for response (should see tokens streaming)
6. Click on a citation

**If this works, you're live! 🎉**

## Troubleshooting (Remaining time)

### "Not authenticated" error
- ✅ Clear browser cookies (F12 → Application → Cookies → delete)
- ✅ Try incognito mode
- ✅ Check CORS is configured (step 3)

### "Connection refused" or "Cannot reach backend"
- ✅ Check backend service is running (visit `/health`)
- ✅ Check VITE_API_BASE_URL exactly matches backend URL
- ✅ Check ALLOWED_ORIGINS includes frontend URL

### "Streaming stuck" or "Error generating response"
- ✅ Check OpenAI API key is valid and has credit
- ✅ Check DATABASE_URL is correct
- ✅ Check logs for error messages

### "No documents found"
- ⚠️ You need to ingest documents (see docs/guides/data-ingestion.md)
- For MVP, this is expected — add sample data later

## Post-Launch Checklist

- [ ] Test register → login → chat → cite flow
- [ ] Check Railway dashboard for errors
- [ ] Set spending alert (Railway → Team Settings → Billing → set limit to $50/week)
- [ ] Share URL with stakeholders
- [ ] Document: how to restart services, check logs, deploy updates

## Deploy Updates (going forward)

1. Push code to GitHub: `git push`
2. Railway auto-redeploys (3-5 min)
3. Check logs to verify deploy succeeded

## Rollback (if something breaks)

1. In Railway, go to "Deployments"
2. Click the previous version
3. Click "Redeploy"

---

**Questions?** Check Railway docs: https://docs.railway.app
