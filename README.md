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
- **Real-time RTSP Stream Processing** - Connect unlimited IP cameras
- **AI Object Detection** - YOLOv8+ with support for custom trained models
- **Automatic Event Creation** - Background service auto-detects and saves events
- **Event Summarization** - Vision LLM (Ollama) powered scene descriptions
- **Multi-user Support** - Role-based access (Admin/Operator/Viewer)
- **AI Assistant** - Query surveillance events using natural language
- **Persistent Settings** - User preferences saved to database

### Detection Features
- 🎯 Custom YOLO model upload and management
- 📊 Confidence threshold configuration
- 🔍 Filter by object classes (person, car, fire, smoke, etc.)
- ⏱️ Configurable detection cooldown
- 🖼️ Frame snapshot with bounding boxes

### AI Features
- 🤖 Multiple Ollama model support (auto-fetch available models)
- 💬 Vision-Language Model integration for scene analysis
- 🧠 Chat assistant with conversation history
- 📷 Image analysis with event context

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
- Docker & Docker Compose (recommended)
- Python 3.10+ (for manual setup)
- Node.js 18+ (for manual setup)
- NVIDIA GPU with CUDA (recommended for YOLO inference)
- Ollama server running (local or remote)

### Option 1: Docker Quick Start (Recommended)

```bash
# Clone the repository
git clone https://github.com/ranjanjyoti152/Chowkidaar.git
cd Chowkidaar

# Copy environment file and configure
cp .env.example .env
nano .env  # Edit settings

# Start all services
docker compose up -d

# Database will auto-initialize from init.sql
# Access the app at http://localhost
```

### Option 2: Manual Development Setup

#### 1. Setup PostgreSQL Database
```bash
# Start PostgreSQL container (easiest way)
docker run -d \
  --name chowkidaar-db \
  -e POSTGRES_USER=chowkidaar \
  -e POSTGRES_PASSWORD=chowkidaar123 \
  -e POSTGRES_DB=chowkidaar \
  -p 5533:5432 \
  -v chowkidaar_postgres:/var/lib/postgresql/data \
  postgres:16-alpine

# Initialize database schema
docker exec -i chowkidaar-db psql -U chowkidaar -d chowkidaar < backend/database/init.sql

# Or use existing PostgreSQL:
psql -U postgres -c "CREATE DATABASE chowkidaar;"
psql -U postgres -d chowkidaar < backend/database/init.sql
```

#### 2. Setup Ollama (Vision LLM)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull vision models (choose one or more)
ollama pull llama3.2-vision:11b  # Best for security analysis
ollama pull gemma3:4b             # Lightweight chat model

# Start Ollama server
ollama serve
```

#### 3. Setup Backend
```bash
cd backend

# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << EOF
DATABASE_URL=postgresql+asyncpg://chowkidaar:chowkidaar123@localhost:5533/chowkidaar
SECRET_KEY=your-super-secret-key-change-this
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_VLM_MODEL=llama3.2-vision:11b
OLLAMA_CHAT_MODEL=gemma3:4b
YOLO_MODEL_PATH=yolov8n.pt
YOLO_DEVICE=0
EOF

# Start backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

#### 4. Setup Frontend
```bash
cd frontend

# Install dependencies
npm install

# Create .env file
echo "VITE_API_BASE_URL=http://localhost:8001/api/v1" > .env

# Start development server
npm run dev
```

#### 5. Access Application
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs

#### 6. Create First User
Register through the UI or use API:
```bash
curl -X POST http://localhost:8001/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "email": "admin@example.com", 
    "password": "admin123",
    "full_name": "Admin User"
  }'
```

### Database Schema

The `backend/database/init.sql` file contains the complete database schema:
- **users** - User accounts with roles (admin/operator/viewer)
- **cameras** - RTSP camera configurations
- **events** - Detection events with metadata
- **chat_sessions** - AI assistant chat history
- **chat_messages** - Chat messages
- **user_settings** - Per-user settings (detection, VLM, storage, notifications)

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

### Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/register` | POST | Register new user |
| `/api/v1/auth/login` | POST | Login, get JWT token |
| `/api/v1/auth/me` | GET | Get current user |

### Cameras
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/cameras` | GET/POST | List/Add cameras |
| `/api/v1/cameras/{id}` | GET/PUT/DELETE | Camera CRUD |
| `/api/v1/cameras/{id}/stream/start` | POST | Start camera stream |
| `/api/v1/cameras/{id}/stream/stop` | POST | Stop camera stream |
| `/api/v1/cameras/{id}/frame` | GET | Get current frame (JPEG) |

### Events
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/events` | GET | List detection events |
| `/api/v1/events/{id}` | GET | Event details |
| `/api/v1/events/{id}/image` | GET | Event snapshot image |

### AI Assistant
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/assistant/sessions` | GET/POST | List/Create chat sessions |
| `/api/v1/assistant/sessions/{id}/chat` | POST | Send message to AI |
| `/api/v1/assistant/sessions/{id}/messages` | GET | Get chat history |

### Settings
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/settings` | GET | Get user settings |
| `/api/v1/settings` | PUT | Save user settings |

### System & Models
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/system/stats` | GET | System hardware stats |
| `/api/v1/system/ollama-models` | GET | List Ollama models |
| `/api/v1/system/yolo-models` | GET | List YOLO models |
| `/api/v1/system/yolo-models/upload` | POST | Upload custom YOLO model |
| `/api/v1/system/yolo-models/{name}/classes` | GET | Get model classes |
| `/api/v1/system/yolo-models/{name}/activate` | POST | Activate YOLO model |
| `/api/v1/system/yolo-models/{name}` | DELETE | Delete YOLO model |

### Users (Admin)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/users` | GET/POST | List/Create users |
| `/api/v1/users/{id}` | GET/PUT/DELETE | User CRUD |

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
