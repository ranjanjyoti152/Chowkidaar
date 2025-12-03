# 🛡️ Chowkidaar - Intelligent NVR System

**Chowkidaar** (meaning "Watchman" in Hindi) is an AI-powered Network Video Recorder application that provides intelligent surveillance with real-time object detection, event summarization, and an AI assistant for querying events.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHOWKIDAAR NVR SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────────────────────────────────────────┐  │
│  │   RTSP       │     │              SERVER APPLICATION                   │  │
│  │   CAMERAS    │────▶│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  │  │
│  │              │     │  │   Stream    │  │   YOLOv8+   │  │  Event   │  │  │
│  └──────────────┘     │  │   Handler   │─▶│  Detection  │─▶│ Processor│  │  │
│                       │  └─────────────┘  └─────────────┘  └────┬─────┘  │  │
│                       │                                          │        │  │
│                       │                                          ▼        │  │
│                       │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  │  │
│                       │  │  PostgreSQL │◀─│   Ollama    │◀─│  Frame   │  │  │
│                       │  │   Database  │  │     VLM     │  │ Capturer │  │  │
│                       │  └─────────────┘  └─────────────┘  └──────────┘  │  │
│                       └──────────────────────────────────────────────────┘  │
│                                              │                               │
│                                              ▼                               │
│                       ┌──────────────────────────────────────────────────┐  │
│                       │              REACT FRONTEND                       │  │
│                       │  ┌────────┐ ┌────────┐ ┌────────┐ ┌───────────┐  │  │
│                       │  │Dashboard│ │Cameras │ │Monitor │ │ Assistant │  │  │
│                       │  └────────┘ └────────┘ └────────┘ └───────────┘  │  │
│                       └──────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🚀 Features

### Core Features
- **Real-time RTSP Stream Processing** - Connect multiple IP cameras
- **AI Object Detection** - YOLOv8+ for detecting people, vehicles, fire, smoke, etc.
- **Event Summarization** - VLM-powered intelligent scene description
- **Multi-user Support** - Separate event storage per user session
- **AI Assistant** - Query your surveillance events using natural language

### UI Features
- 🌙 Dark theme with cyan/blue gradient accents
- 🪟 Glass-morphism UI components
- ✨ Smooth animated transitions
- 📱 Fully responsive design

## 📁 Project Structure

```
chowkidaar/
├── backend/                    # FastAPI Backend
│   ├── app/
│   │   ├── api/               # API routes
│   │   │   ├── routes/
│   │   │   │   ├── cameras.py
│   │   │   │   ├── events.py
│   │   │   │   ├── users.py
│   │   │   │   ├── assistant.py
│   │   │   │   ├── system.py
│   │   │   │   └── auth.py
│   │   │   └── deps.py
│   │   ├── core/              # Core configurations
│   │   │   ├── config.py
│   │   │   ├── security.py
│   │   │   └── database.py
│   │   ├── models/            # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── camera.py
│   │   │   ├── event.py
│   │   │   └── summary.py
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   │   ├── stream_handler.py
│   │   │   ├── yolo_detector.py
│   │   │   ├── event_processor.py
│   │   │   ├── ollama_vlm.py
│   │   │   └── system_monitor.py
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                   # React Frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   ├── services/
│   │   ├── store/
│   │   └── styles/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python, FastAPI, Uvicorn |
| AI Detection | YOLOv8+ (Ultralytics) |
| VLM | Ollama (LLaVA, etc.) |
| Frontend | React, TailwindCSS |
| Database | PostgreSQL |
| Streaming | OpenCV, FFmpeg |

## 🚦 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Ollama installed locally
- NVIDIA GPU (recommended for YOLO inference)

### Option 1: Docker (Recommended)

```bash
# Clone the repository
cd /path/to/NVR

# Copy environment file
cp .env.example .env

# Edit .env with your settings (change SECRET_KEY and passwords!)
nano .env

# Start all services (with GPU support)
docker compose up -d

# Or for CPU-only mode:
docker compose -f docker-compose.cpu.yml up -d

# Pull the LLaVA model for Ollama
docker exec -it chowkidaar-ollama ollama pull llava

# Access the application
# Frontend: http://localhost
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option 2: Manual Setup

#### 1. Setup PostgreSQL Database
```bash
# Create database
createdb chowkidaar

# Or using psql
psql -U postgres
CREATE DATABASE chowkidaar;
CREATE USER chowkidaar WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE chowkidaar TO chowkidaar;
\q
```

#### 2. Setup Backend
```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your database URL and settings

# Run database migrations
alembic upgrade head

# Start the backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. Setup Ollama
```bash
# Install Ollama (if not installed)
curl -fsSL https://ollama.com/install.sh | sh

# Pull the LLaVA vision model
ollama pull llava

# Start Ollama server (usually runs automatically)
ollama serve
```

#### 4. Setup Frontend
```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

#### 5. Create Admin User
```bash
# The first registered user automatically becomes admin
# Or use the API to create one:
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "admin@example.com", "password": "your_password"}'
```

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | - |
| `SECRET_KEY` | JWT secret key | - |
| `OLLAMA_BASE_URL` | Ollama server URL | http://localhost:11434 |
| `OLLAMA_MODEL` | Vision model name | llava |
| `YOLO_MODEL` | YOLO model file | yolov8n.pt |
| `YOLO_DEVICE` | Inference device (0=GPU, cpu) | 0 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT token expiry | 30 |

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/cameras` | GET/POST | List/Add cameras |
| `/api/v1/cameras/{id}` | GET/PUT/DELETE | Camera operations |
| `/api/v1/cameras/{id}/stream` | GET | Get camera stream |
| `/api/v1/events` | GET | List detected events |
| `/api/v1/events/{id}` | GET | Event details |
| `/api/v1/assistant/chat` | POST | Chat with AI assistant |
| `/api/v1/system/stats` | GET | System hardware stats |
| `/api/v1/users` | GET/POST | User management |
| `/api/v1/auth/login` | POST | User authentication |

## 🔒 Security

- JWT-based authentication
- Role-based access control (RBAC)
- Secure password hashing (bcrypt)
- CORS protection

## 📄 License

MIT License - See LICENSE file for details.

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines.

---

**Chowkidaar** - Your AI-powered digital watchman 🛡️
