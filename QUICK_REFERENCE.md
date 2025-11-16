# RDFMap Web UI - Quick Reference Card

## 🚀 Start/Stop

```bash
# Start everything
docker compose up -d

# Stop everything
docker compose down

# Restart specific service
docker compose restart api
docker compose restart ui
docker compose restart worker
```

## 🌐 Access URLs

- **Frontend UI:** http://localhost:8080 or http://localhost:5173
- **API Docs:** http://localhost:8000/api/docs
- **Health Check:** http://localhost:8000/api/health

## 📊 Monitor

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f api
docker compose logs -f worker
docker compose logs -f ui

# Check status
docker compose ps
```

## 🧪 Test

```bash
# Test API
curl http://localhost:8000/api/health

# Test Celery worker
docker compose exec api python3 -c "from app.worker import test_task; print(test_task.delay().get())"

# Create a project
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "Test", "description": "Test project"}'
```

## 🔧 Develop

```bash
# Enter containers
docker compose exec api bash
docker compose exec ui sh

# Restart after code changes
docker compose restart api

# Rebuild after dependency changes
docker compose build api
docker compose up -d api
```

## 🗑️ Clean Up

```bash
# Stop (keep data)
docker compose down

# Stop + remove data
docker compose down -v

# Full rebuild
docker compose down -v
docker compose build --no-cache
docker compose up -d
```

## 📦 What's Running

- **api** - FastAPI backend (port 8000)
- **ui** - React frontend (ports 8080, 5173)
- **db** - PostgreSQL database (port 5432)
- **redis** - Redis cache/queue (port 6379)
- **worker** - Celery background jobs

## ✅ All Systems Operational!

See `ALL_SYSTEMS_GO.md` for complete details.

