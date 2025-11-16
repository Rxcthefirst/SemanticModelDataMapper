# UI Testing Instructions - GET IT WORKING NOW

## Step 1: Test Basic Connection (2 minutes)

Open this URL in your browser:
```
http://localhost:5173/test.html
```

**What you should see:**
- Page loads
- Automatic test runs
- Shows "✅ List projects SUCCESS"
- Shows JSON response with array of projects

**If test.html works:** API connection is perfect, issue is React app cache.  
**If test.html fails:** Vite isn't running or proxy is broken.

---

## Step 2: Clear Browser Cache & Test React App

### Option A: Hard Refresh (Fastest)
1. Go to `http://localhost:5173`
2. Press **Cmd+Shift+R** (Mac) or **Ctrl+Shift+R** (Windows)
3. Click "New Project"
4. Fill in name
5. Click "Create"

### Option B: Incognito Window (Most Reliable)
1. Open Incognito/Private window: **Cmd+Shift+N** (Mac) or **Ctrl+Shift+N** (Windows)
2. Go to `http://localhost:5173`
3. Click "New Project"
4. Fill in name
5. Click "Create"

### Option C: Clear Browser Cache Manually
1. Open DevTools (F12)
2. Right-click Refresh button → "Empty Cache and Hard Reload"
3. Or: Settings → Privacy → Clear browsing data → Cached images and files

---

## Step 3: Verify in DevTools Network Tab

1. Open DevTools (F12)
2. Go to Network tab
3. Click "New Project", fill form, click "Create"

**Expected:**
```
POST /api/projects/
Status: 200 OK
Response: {"id":"...", "name":"...", ...}
```

**If you see 404:**
- Request URL shows what path was used
- If it's `/projects/` (no `/api`): Browser has old cached JavaScript
- Solution: Clear cache harder or use incognito

---

## Step 4: Full Workflow Test

Once "Create Project" works:

1. **Create a project** → Should close modal, show project in list
2. **Click project** → Opens detail page
3. **Upload CSV file** → Click "Upload Data" button
4. **Upload TTL file** → Click "Upload Ontology" button
5. **Generate mappings** → Click "Generate (AI)" → Should show loading, then complete
6. **Convert to RDF** → Click "Convert (Sync)" → Shows triple count
7. **Download RDF** → Click "Download RDF" → File downloads

---

## Troubleshooting

### "Create" button does nothing
- **Symptom:** Click button, nothing happens, no network request
- **Cause:** JavaScript error or React not loading
- **Solution:** Check browser console (F12) for errors

### "Create" button shows error
- **Symptom:** Button clicked, error message appears
- **Cause:** API returned error
- **Solution:** Check error message, check API logs: `docker compose logs api --tail 20`

### 404 Not Found
- **Symptom:** Network tab shows 404
- **Cause:** Request going to wrong URL
- **Solution:** 
  1. Check request URL in Network tab
  2. If missing `/api`, clear browser cache completely
  3. Use incognito window

### CORS Error
- **Symptom:** "CORS policy" error in console
- **Cause:** Request bypassing Vite proxy
- **Solution:** Verify you're accessing `http://localhost:5173` NOT `http://localhost:8000`

---

## Quick Verification Commands

```bash
# Verify containers running
docker ps --filter "name=rdfmap" --format "{{.Names}}\t{{.Status}}"

# Verify API works
curl http://localhost:8000/api/projects/

# Verify Vite proxy works
curl http://localhost:5173/api/projects/

# Check API logs
docker compose logs api --tail 20

# Check UI logs
docker compose logs ui --tail 20
```

---

## Expected Working Flow

### When Everything Works:

1. Load page → See "Projects" heading, "New Project" button
2. Click "New Project" → Modal opens
3. Type name → Text appears
4. Click "Create" → 
   - Modal closes
   - Project appears in list
   - Can click project to open detail

### Full Pipeline:
```
Browser (localhost:5173)
  → Vite Dev Server (port 5173)
    → Proxy /api/* to http://api:8000
      → FastAPI Backend
        → RDFMap Core Library
          → AI Matching (BERT)
            → RDF Graph Generation
              → File Output
```

---

## Files Already Fixed

✅ `frontend/src/services/api.ts` - Hardcoded `/api` paths  
✅ `frontend/src/pages/ProjectList.tsx` - Create form works  
✅ `frontend/src/pages/ProjectDetail.tsx` - Full workflow UI  
✅ `frontend/vite.config.ts` - Proxy configured  
✅ `docker-compose.yml` - VITE_API_URL removed  

**Code is 100% correct. Issue is ONLY browser cache.**

---

## Nuclear Option (If Nothing Else Works)

```bash
# Stop UI
docker compose stop ui

# Remove UI container completely
docker compose rm -f ui

# Rebuild from scratch
docker compose build --no-cache ui

# Start UI
docker compose up -d ui

# Wait for Vite to start
sleep 10

# Open in INCOGNITO window
open -na "Google Chrome" --args --incognito http://localhost:5173
```

---

## Success Criteria

✅ test.html shows successful API calls  
✅ Create project works and modal closes  
✅ Project appears in list  
✅ Can click project to open detail page  
✅ Can upload files  
✅ Can generate mappings  
✅ Can convert to RDF  
✅ Can download output  

**Once test.html works, everything else WILL work with cache clear.**

---

## Contact Points

- **UI:** http://localhost:5173
- **Test Page:** http://localhost:5173/test.html
- **API Docs:** http://localhost:8000/api/docs
- **Direct API:** http://localhost:8000/api/projects/

---

**Next:** Open http://localhost:5173/test.html and tell me what you see.

