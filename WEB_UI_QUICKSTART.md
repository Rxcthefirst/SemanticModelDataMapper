# RDFMap Web UI - Quick Start Guide

🎉 **Welcome to the RDFMap Web UI!**

This is a containerized web application (like Neo4j) that provides a modern UI for RDFMap - the AI-powered semantic data mapper.

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Docker Compose                     │
│                                                 │
│  ┌─────────┐  ┌─────────┐  ┌──────────────┐  │
│  │   UI    │─▶│   API   │─▶│  PostgreSQL  │  │
│  │ (React) │  │(FastAPI)│  │              │  │
│  │  :8080  │  │  :8000  │  │    :5432     │  │
│  └─────────┘  └─────────┘  └──────────────┘  │
│                     │                          │
│                     ▼                          │
│              ┌──────────┐                      │
│              │  Redis   │                      │
│              │  :6379   │                      │
│              └──────────┘                      │
└─────────────────────────────────────────────────┘
```

## Prerequisites

- **Docker** and **Docker Compose** installed
- **8GB RAM** minimum (16GB recommended)
- **Ports available:** 8080 (UI), 8000 (API), 5432 (DB), 6379 (Redis)

## Quick Start (5 Minutes)

### Step 1: Start the Application

```bash
# From the project root
docker-compose up -d
```

This will:
- ✅ Build backend API (FastAPI)
- ✅ Build frontend UI (React)
- ✅ Start PostgreSQL database
- ✅ Start Redis cache
- ✅ Initialize all services

### Step 2: Wait for Services

```bash
# Check status
docker-compose ps

# Watch logs
docker-compose logs -f api
```

Wait for: `🚀 RDFMap Web API started`

### Step 3: Open the UI

Navigate to: **http://localhost:8080**

You should see the RDFMap project dashboard!

### Step 4: Test the API

```bash
# Check health
curl http://localhost:8000/api/health

# View API docs (Swagger UI)
open http://localhost:8000/api/docs
```

## What You Can Do Now

### 1. Create a Project
- Click "New Project"
- Enter name and description
- Click "Create"

### 2. Upload Files
- Upload your data file (CSV, Excel, JSON, XML)
- Upload your ontology (TTL, OWL, RDF/XML)

### 3. Generate Mappings (Coming Soon)
- AI will automatically suggest column-to-property mappings
- Review and edit in visual editor
- Accept/reject suggestions

### 4. Convert to RDF (Coming Soon)
- Click "Convert"
- Download RDF output
- View validation report

## Development

### Backend Development

```bash
# Enter backend container
docker-compose exec api bash

# Run tests
pytest

# Check logs
docker-compose logs -f api
```

### Frontend Development

```bash
# Enter frontend container
docker-compose exec ui sh

# Or run locally
cd frontend
npm install
npm run dev
```

Visit: http://localhost:5173 (Vite dev server with hot reload)

### Watch All Logs

```bash
docker-compose logs -f
```

## Project Structure

```
SemanticModelDataMapper/
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── main.py          # FastAPI app
│   │   ├── config.py        # Settings
│   │   ├── routers/         # API endpoints
│   │   │   ├── projects.py
│   │   │   ├── mappings.py
│   │   │   └── conversion.py
│   │   └── schemas/         # Pydantic models
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                 # React frontend
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml        # Multi-container setup
└── docs/
    └── WEB_UI_ARCHITECTURE.md  # Detailed architecture doc
```

## Current Status

### ✅ Working Now
- [x] Docker Compose setup
- [x] FastAPI backend with health check
- [x] React frontend scaffolding
- [x] Project CRUD endpoints
- [x] File upload (data + ontology)
- [x] PostgreSQL database
- [x] Redis caching
- [x] API documentation (Swagger)

### 🚧 In Progress
- [ ] Integration with RDFMap core library
- [ ] Mapping generation endpoint
- [ ] Visual mapping editor (React Flow)
- [ ] RDF conversion endpoint
- [ ] WebSocket real-time updates
- [ ] Ontology graph visualization

### 🎯 Coming Soon
- [ ] Authentication (JWT)
- [ ] User management
- [ ] Template gallery
- [ ] Validation dashboard
- [ ] RDF preview panel
- [ ] Export/import configurations

## API Endpoints

### Projects
```
POST   /api/projects                     Create project
GET    /api/projects                     List projects
GET    /api/projects/{id}               Get project
DELETE /api/projects/{id}               Delete project
POST   /api/projects/{id}/upload-data   Upload data file
POST   /api/projects/{id}/upload-ontology  Upload ontology
GET    /api/projects/{id}/data-preview  Preview data
```

### Mappings (Coming Soon)
```
POST   /api/mappings/{project_id}/generate    Auto-generate mappings
GET    /api/mappings/{project_id}            Get mappings
PUT    /api/mappings/{project_id}/{col}      Update mapping
```

### Conversion (Coming Soon)
```
POST   /api/conversion/{project_id}          Convert to RDF
GET    /api/conversion/{project_id}/status   Check status
GET    /api/conversion/{project_id}/download Download RDF
```

### WebSockets (Coming Soon)
```
WS     /ws/{project_id}                      Real-time updates
```

## Troubleshooting

### Port Already in Use

```bash
# Change ports in docker-compose.yml
ports:
  - "9080:80"   # Instead of 8080
  - "9000:8000" # Instead of 8000
```

### Services Won't Start

```bash
# Stop and remove everything
docker-compose down -v

# Rebuild
docker-compose build --no-cache

# Start again
docker-compose up -d
```

### Can't Connect to API

```bash
# Check API is running
docker-compose ps api

# Check API logs
docker-compose logs api

# Try accessing directly
curl http://localhost:8000/api/health
```

### Database Issues

```bash
# Reset database
docker-compose down -v  # Removes volumes!
docker-compose up -d
```

## Configuration

### Environment Variables

Create `.env` file in project root:

```bash
# API Settings
API_PORT=8000
CORS_ORIGINS=http://localhost:8080,http://localhost:5173

# Database
POSTGRES_USER=rdfmap
POSTGRES_PASSWORD=change-me-in-production
POSTGRES_DB=rdfmap

# Redis
REDIS_PASSWORD=

# RDFMap Settings
RDFMAP_USE_SEMANTIC=true
RDFMAP_SEMANTIC_THRESHOLD=0.7
RDFMAP_MIN_CONFIDENCE=0.5

# Security (IMPORTANT!)
SECRET_KEY=generate-with-openssl-rand-hex-32
```

### Generate Secret Key

```bash
openssl rand -hex 32
```

## Next Steps

### For Developers

1. **Integrate RDFMap Core**
   - Import `rdfmap` in backend
   - Wire up `MappingGenerator` in `/api/mappings/generate`
   - Add `RDFGraphBuilder` in `/api/conversion`

2. **Build Visual Mapping Editor**
   - Install React Flow
   - Create column/property nodes
   - Add drag-drop connections

3. **Add Real-Time Updates**
   - Implement WebSocket handlers
   - Send progress events during conversion
   - Update UI in real-time

### For Users

1. **Try the Mortgage Example**
   - Upload `examples/mortgage/data/loans.csv`
   - Upload `examples/mortgage/ontology/mortgage.ttl`
   - Click "Generate Mappings" (when implemented)
   - Review and convert

2. **Explore Templates**
   - Browse pre-built templates
   - Use for quick start
   - Customize for your domain

## Support

- **Documentation:** [WEB_UI_ARCHITECTURE.md](docs/WEB_UI_ARCHITECTURE.md)
- **API Docs:** http://localhost:8000/api/docs
- **Issues:** GitHub Issues (when published)

## Roadmap

See [WEB_UI_ARCHITECTURE.md](docs/WEB_UI_ARCHITECTURE.md) for:
- Detailed feature plan
- Phase-by-phase implementation
- Technology choices
- UI/UX mockups

**Timeline:** 6-8 weeks to full MVP

---

## Quick Commands Reference

```bash
# Start everything
docker-compose up -d

# Stop everything
docker-compose down

# View logs
docker-compose logs -f

# Restart a service
docker-compose restart api

# Rebuild after code changes
docker-compose build api
docker-compose up -d api

# Enter a container
docker-compose exec api bash
docker-compose exec ui sh

# Clean slate (removes data!)
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

---

**🎉 Welcome to RDFMap Web!** You're now running a Neo4j-style containerized semantic data mapper with AI-powered intelligence.

Next: Check out the [Architecture Guide](docs/WEB_UI_ARCHITECTURE.md) for the full roadmap.

