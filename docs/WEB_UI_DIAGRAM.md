# RDFMap Web UI - Architecture Diagram

## Complete System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                                                             │
│                          🌐 User's Browser                                  │
│                                                                             │
└────────────────────────────────┬────────────────────────────────────────────┘
                                 │
                                 │ HTTP/WebSocket
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Docker Compose Network                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                     Frontend (UI Container)                         │  │
│  │  • nginx:alpine (production) or Vite dev server                     │  │
│  │  • React 18 + TypeScript                                            │  │
│  │  • Material-UI components                                           │  │
│  │  • React Flow (visual mapper)                                       │  │
│  │  • Cytoscape.js (ontology graph)                                    │  │
│  │  • Port: 8080 (nginx) / 5173 (dev)                                 │  │
│  └────────────────────────┬────────────────────────────────────────────┘  │
│                           │                                                 │
│                           │ REST API / WebSocket                            │
│                           ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                     Backend (API Container)                         │  │
│  │  • Python 3.11 + FastAPI                                            │  │
│  │  • Uvicorn ASGI server                                              │  │
│  │  • RDFMap Core Library                                              │  │
│  │    - MappingGenerator (11 matchers)                                 │  │
│  │    - OntologyAnalyzer                                               │  │
│  │    - RDFGraphBuilder                                                │  │
│  │  • Celery workers (background jobs)                                 │  │
│  │  • Port: 8000                                                       │  │
│  └────┬──────────────────┬─────────────────┬──────────────────────────┘  │
│       │                  │                 │                               │
│       │                  │                 │                               │
│       ▼                  ▼                 ▼                               │
│  ┌─────────┐      ┌─────────────┐   ┌──────────┐                         │
│  │Database │      │    Redis    │   │  Worker  │                         │
│  │Container│      │  Container  │   │Container │                         │
│  │         │      │             │   │          │                         │
│  │Postgres │      │ Cache/Queue │   │  Celery  │                         │
│  │  16     │      │             │   │          │                         │
│  │         │      │             │   │          │                         │
│  │Port:    │      │Port:        │   │Background│                         │
│  │ 5432    │      │ 6379        │   │  Jobs    │                         │
│  └─────────┘      └─────────────┘   └──────────┘                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Project Creation Flow
```
User → UI → POST /api/projects → API → Database
                                  ↓
                            Create project folder
                                  ↓
                            Return project ID
```

### 2. File Upload Flow
```
User → UI → File Upload Component → POST /api/projects/{id}/upload-data
                                              ↓
                                     Validate file type
                                              ↓
                                     Save to /uploads/{project_id}/
                                              ↓
                                     Update database
                                              ↓
                                     Return file info
```

### 3. Mapping Generation Flow (When Implemented)
```
User → UI → "Generate" button → POST /api/mappings/{id}/generate
                                         ↓
                                   Load ontology (OntologyAnalyzer)
                                         ↓
                                   Load data (DataSourceAnalyzer)
                                         ↓
                                   Run MappingGenerator
                                    - 11 intelligent matchers
                                    - BERT semantic matching
                                    - Graph reasoning
                                         ↓
                                   Generate alignment report
                                         ↓
                                   Store in database
                                         ↓
                                   Return mappings + confidence
                                         ↓
                                   UI displays visual editor
```

### 4. RDF Conversion Flow (When Implemented)
```
User → UI → "Convert" button → POST /api/conversion/{id}
                                         ↓
                                   Create Celery job
                                         ↓
                                   Background worker picks up
                                         ↓
                                   Load mapping config
                                         ↓
                                   Parse data (Polars)
                                         ↓
                                   Build RDF graph
                                    - Apply IRI templates
                                    - Create triples
                                    - Link objects
                                         ↓
                                   Serialize to file
                                         ↓
                                   Update job status
                                         ↓
                                   WebSocket → UI (real-time update)
                                         ↓
                                   User downloads RDF
```

## Technology Stack Details

### Frontend Stack
```
React 18.2
  ├── TypeScript 5.3
  ├── React Router 6.20 (navigation)
  ├── React Query 5.12 (API state)
  ├── Material-UI 5.14 (components)
  ├── React Flow 11.10 (visual mapper)
  ├── Cytoscape.js 3.28 (graph viz)
  ├── Axios 1.6 (HTTP client)
  └── Zustand 4.4 (UI state)
```

### Backend Stack
```
FastAPI 0.104
  ├── Uvicorn 0.24 (ASGI server)
  ├── Pydantic 2.5 (validation)
  ├── SQLAlchemy 2.0 (ORM)
  ├── Alembic 1.12 (migrations)
  ├── Celery 5.3 (async jobs)
  ├── Redis 5.0 (broker/cache)
  └── RDFMap Core
       ├── RDFLib 7.0
       ├── Polars 0.19
       ├── Sentence-Transformers 2.2
       └── PyShacl 0.25
```

### Infrastructure Stack
```
Docker Compose 3.8
  ├── Frontend Container (Node 20 → nginx)
  ├── Backend Container (Python 3.11)
  ├── Worker Container (Python 3.11 + Celery)
  ├── Database Container (PostgreSQL 16)
  └── Cache Container (Redis 7)
```

## API Endpoints Map

```
/                              GET     Root endpoint
/api/health                    GET     Health check

/api/projects                  GET     List all projects
/api/projects                  POST    Create project
/api/projects/{id}            GET     Get project details
/api/projects/{id}            PUT     Update project
/api/projects/{id}            DELETE  Delete project
/api/projects/{id}/upload-data         POST    Upload data file
/api/projects/{id}/upload-ontology     POST    Upload ontology
/api/projects/{id}/data-preview        GET     Preview data (first N rows)

/api/mappings/{id}            GET     Get project mappings
/api/mappings/{id}/generate   POST    Auto-generate mappings
/api/mappings/{id}/column     PUT     Update single mapping
/api/mappings/{id}/accept     POST    Accept suggestions
/api/mappings/{id}/reject     POST    Reject suggestions

/api/conversion/{id}          POST    Start RDF conversion
/api/conversion/{id}/status   GET     Check conversion status
/api/conversion/{id}/download GET     Download RDF file
/api/conversion/{id}/preview  GET     Preview RDF (first N triples)
/api/conversion/{id}/validate POST    Validate against ontology

/ws/{project_id}              WS      Real-time updates
```

## Component Architecture

### Frontend Components
```
src/
├── App.tsx                    # Main app with routing
├── components/
│   ├── layout/
│   │   ├── Layout.tsx         # App shell
│   │   ├── Header.tsx         # Top navigation
│   │   └── Sidebar.tsx        # Side navigation
│   ├── projects/
│   │   ├── ProjectCard.tsx    # Project tile
│   │   ├── ProjectList.tsx    # Project grid
│   │   └── CreateProject.tsx  # Creation dialog
│   ├── upload/
│   │   ├── FileUpload.tsx     # Drag-drop uploader
│   │   └── FileValidator.tsx  # Type validation
│   ├── mapping/
│   │   ├── MappingEditor.tsx  # React Flow canvas
│   │   ├── ColumnNode.tsx     # Data column node
│   │   ├── PropertyNode.tsx   # Ontology property node
│   │   ├── ConnectionEdge.tsx # Mapping connection
│   │   └── ReviewTable.tsx    # Tabular review
│   ├── ontology/
│   │   ├── OntologyGraph.tsx  # Cytoscape graph
│   │   └── ClassInspector.tsx # Property details
│   ├── rdf/
│   │   ├── RDFPreview.tsx     # Monaco editor
│   │   └── ValidationDash.tsx # SHACL results
│   └── templates/
│       ├── TemplateGallery.tsx # Browse templates
│       └── TemplateCard.tsx    # Template info
├── hooks/
│   ├── useProjects.ts         # Project CRUD hooks
│   ├── useMappings.ts         # Mapping hooks
│   └── useWebSocket.ts        # Real-time updates
└── services/
    └── api.ts                  # API client wrapper
```

### Backend Services
```
app/
├── main.py                    # FastAPI app
├── config.py                  # Settings
├── routers/
│   ├── projects.py            # Project endpoints
│   ├── mappings.py            # Mapping endpoints
│   ├── conversion.py          # Conversion endpoints
│   └── websockets.py          # WebSocket handlers
├── services/
│   ├── rdfmap_service.py      # RDFMap core wrapper
│   ├── file_service.py        # File operations
│   └── validation_service.py  # SHACL validation
├── models/
│   ├── project.py             # SQLAlchemy models
│   ├── mapping.py
│   └── job.py
├── schemas/
│   ├── project.py             # Pydantic schemas
│   ├── mapping.py
│   └── responses.py
└── utils/
    ├── logging.py
    └── exceptions.py
```

## Deployment Architecture

### Development (Current)
```
Docker Compose on localhost
  • Hot reload enabled
  • Debug mode on
  • No SSL
  • SQLite for rapid iteration
```

### Production (Future)
```
Cloud Platform (AWS/GCP/Azure/DigitalOcean)
  ├── Load Balancer (SSL termination)
  │   └── Multiple UI instances
  ├── API Gateway
  │   └── Multiple API instances (auto-scale)
  ├── Managed Database (RDS/Cloud SQL)
  ├── Managed Cache (ElastiCache/Memorystore)
  └── Object Storage (S3/GCS) for uploaded files
```

## Security Layers

```
┌─────────────────────────────────────────┐
│ 1. Network Layer (Docker Network)       │
│    • Isolated internal network          │
│    • Only nginx exposed externally      │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│ 2. API Layer (FastAPI)                  │
│    • CORS whitelist                     │
│    • Rate limiting                      │
│    • JWT authentication (planned)       │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│ 3. Input Validation (Pydantic)          │
│    • Schema validation                  │
│    • Type checking                      │
│    • File type validation               │
└─────────────────────────────────────────┘
┌─────────────────────────────────────────┐
│ 4. Data Layer (SQLAlchemy ORM)          │
│    • Parameterized queries              │
│    • SQL injection prevention           │
└─────────────────────────────────────────┘
```

## Monitoring & Observability (Planned)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Prometheus  │←───│   FastAPI    │    │    Grafana   │
│   (Metrics)  │    │  Exporters   │───→│ (Dashboards) │
└──────────────┘    └──────────────┘    └──────────────┘

┌──────────────┐    ┌──────────────┐
│     Logs     │←───│   Logging    │
│  (Loki/ELK)  │    │  Framework   │
└──────────────┘    └──────────────┘

┌──────────────┐    ┌──────────────┐
│   Tracing    │←───│    OpenTel   │
│   (Jaeger)   │    │  Integration │
└──────────────┘    └──────────────┘
```

---

## Getting Started Commands

```bash
# Start everything
./start-web-ui.sh

# Or manually
docker-compose up -d

# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Reset (delete all data)
docker-compose down -v
```

---

**📚 For more details, see:**
- `WEB_UI_QUICKSTART.md` - Getting started guide
- `docs/WEB_UI_ARCHITECTURE.md` - Complete architecture document (60+ pages)
- `COMPREHENSIVE_EVALUATION.md` - Application evaluation

**🎉 You're ready to build the future of semantic data mapping!**

