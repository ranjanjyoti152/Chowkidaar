# 🛡️ Chowkidar - Intelligent NVR System

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?style=for-the-badge&logo=typescript&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![YOLOv8](https://img.shields.io/badge/YOLOv8-Computer%20Vision-blue?style=for-the-badge)
![Ollama](https://img.shields.io/badge/Ollama-Local%20LLM-black?style=for-the-badge)

</div>

**Chowkidar** (meaning "Watchman" in Hindi) is an **advanced AI-powered Network Video Recorder** application that provides intelligent surveillance with real-time object detection, event summarization, and an AI assistant for querying events.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CHOWKIDAR NVR SYSTEM                              │
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

### 🔥 Advanced Analytics (New)
- **Spatial Heatmaps**: Real-time **canvas-based heat overlays** showing high-activity zones on camera feeds.
- **Persistent Object Tracking**: Integrated **ByteTrack** for robust object ID tracking across frames.
- **Dynamic Class Filtering**: Filter heatmap data by specific object classes (person, car, etc.) fetched directly from the active model.
- **Auto-Resolution Sync**: Backend automatically detects and adapts to camera stream resolution for precise data mapping.

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
chowkidar/
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
| Streaming | OpenCV (CUDA), FFmpeg |

## 🎮 GPU Acceleration (CUDA)

Chowkidar supports **GPU-accelerated video streaming** using NVIDIA CUDA for maximum performance with multiple camera streams.

### Features
- 🚀 **CUDA Hardware Video Decoding** - NVCUVID for H.264/H.265 streams
- 🎯 **GPU-Accelerated YOLO Inference** - Faster object detection
- 🔥 **Multi-GPU Support** - Tested with 2x NVIDIA RTX A4500

### Prerequisites
- NVIDIA GPU with Compute Capability 6.0+ (RTX/GTX 10xx or newer)
- NVIDIA Driver 550+ 
- CUDA Toolkit 12.x
- cuDNN 9.x

### Building OpenCV with CUDA Support

Chowkidar includes a script to compile OpenCV from source with full CUDA support:

```bash
# Navigate to scripts directory
cd scripts

# Run the installation script
./install_opencv_cuda.sh
```

The script will:
1. ✅ Detect your GPU architecture automatically
2. ✅ Install all required dependencies
3. ✅ Setup NVIDIA Video Codec SDK headers
4. ✅ Compile OpenCV 4.x with CUDA, cuDNN, NVCUVID, and NVCUVENC
5. ✅ Verify the installation

### NVIDIA Video Codec SDK

The project includes **Video Codec SDK 13.0.19** for hardware video encoding/decoding:

```
Video_Codec_SDK_13.0.19/
├── Interface/          # Header files (nvcuvid.h, cuviddec.h, nvEncodeAPI.h)
├── Samples/            # Sample applications
└── Lib/                # Libraries (Windows only, Linux uses driver libs)
```

Headers are automatically copied to CUDA include directory by the install script.

### Verify CUDA Installation

```python
import cv2

# Check OpenCV version
print(f"OpenCV Version: {cv2.__version__}")

# Check CUDA devices
devices = cv2.cuda.getCudaEnabledDeviceCount()
print(f"CUDA Enabled Devices: {devices}")

# Check Video Codec support
has_cudacodec = hasattr(cv2, 'cudacodec')
print(f"CUDA Video Codec: {has_cudacodec}")

# Print CUDA build info
info = cv2.getBuildInformation()
for line in info.split('\n'):
    if 'CUDA' in line or 'cuDNN' in line:
        print(line)
```

Expected output with CUDA enabled:
```
OpenCV Version: 4.13.0-pre
CUDA Enabled Devices: 2
CUDA Video Codec: True
NVIDIA CUDA: YES (ver 12.4, CUFFT CUBLAS NVCUVID NVCUVENC FAST_MATH)
cuDNN: YES (ver 9.0.0)
```

### CPU Fallback

If CUDA is not available, Chowkidar automatically falls back to CPU video decoding. You'll see in logs:
- `[🚀 CUDA]` - Using GPU hardware decoding
- `[💻 CPU]` - Using CPU software decoding

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
git clone https://github.com/ranjanjyoti152/Chowkidar.git
cd Chowkidar

# Copy environment file and configure
cp .env.example .env
nano .env  # Edit settings

# Start all services
docker compose up -d

# Database will auto-initialize from init.sql
# Access the app at http://localhost
```

### Option 2: Manual Development Setup (Without Docker)

#### 1. Setup PostgreSQL Database

**Option A: Using Docker for PostgreSQL only (Recommended)**
```bash
# Start PostgreSQL container
docker run -d \
  --name chowkidar-db \
  -e POSTGRES_USER=chowkidar \
  -e POSTGRES_PASSWORD=ChowkidarSecure123 \
  -e POSTGRES_DB=chowkidar \
  -p 5533:5432 \
  -v chowkidar_postgres:/var/lib/postgresql/data \
  postgres:16-alpine

# Initialize database schema
docker exec -i chowkidar-db psql -U chowkidar -d chowkidar < backend/database/init.sql
```

**Option B: Using System PostgreSQL**
```bash
# Install PostgreSQL (Ubuntu/Debian)
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql << EOF
CREATE USER chowkidar WITH PASSWORD 'ChowkidarSecure123';
CREATE DATABASE chowkidar OWNER chowkidar;
GRANT ALL PRIVILEGES ON DATABASE chowkidar TO chowkidar;
EOF

# Initialize schema
PGPASSWORD=ChowkidarSecure123 psql -h localhost -U chowkidar -d chowkidar < backend/database/init.sql
```

#### 2. Setup Ollama (Vision LLM)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull vision models (choose one or more)
ollama pull llama3.2-vision:11b  # Best for security analysis
ollama pull gemma3:4b             # Lightweight chat model

# Start Ollama server (runs on port 11434)
ollama serve

# For remote Ollama server, note the IP (e.g., http://192.168.1.100:11434)
```

#### 3. Setup Backend (FastAPI + Uvicorn)
```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# OR: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Create .env file
cat > .env << 'EOF'
# Application
APP_NAME=Chowkidar
DEBUG=true
SECRET_KEY=your-super-secret-key-change-in-production

# Database (adjust port if using system PostgreSQL: 5432)
DATABASE_URL=postgresql+asyncpg://chowkidar:ChowkidarSecure123@localhost:5533/chowkidar
DATABASE_SYNC_URL=postgresql+psycopg2://chowkidar:ChowkidarSecure123@localhost:5533/chowkidar

# JWT
JWT_SECRET_KEY=jwt-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Ollama (update IP if remote)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_VLM_MODEL=gemma3:4b
OLLAMA_CHAT_MODEL=gemma3:4b

# YOLO
YOLO_MODEL_PATH=yolov8n.pt
YOLO_CONFIDENCE_THRESHOLD=0.5

# Storage paths
BASE_PATH=/path/to/your/NVR/backend
FRAMES_STORAGE_PATH=/path/to/your/NVR/backend/storage/frames
EVENTS_STORAGE_PATH=/path/to/your/NVR/backend/storage/events

# CORS
CORS_ORIGINS=*
EOF

# Create storage directories
mkdir -p storage/frames storage/events

# Start backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Backend will run at: http://localhost:8001
# API Docs at: http://localhost:8001/docs
```

#### 4. Setup Frontend (React + Vite)

Open a **new terminal**:
```bash
cd frontend

# Install Node.js dependencies
npm install

# Create .env file
cat > .env << 'EOF'
VITE_API_URL=http://localhost:8001
EOF

# Start frontend development server
npm run dev

# Frontend will run at: http://localhost:5173
```

#### 5. Running Both Together

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

#### 6. Access Application
| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8001 |
| API Documentation | http://localhost:8001/docs |
| Ollama | http://localhost:11434 |

#### 7. Create First Admin User

**Via API:**
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

**Or via Frontend:** Go to http://localhost:5173 and click "Register"

#### 8. Add Your First Camera

After login, go to **Cameras** page and add:
- **Name:** Front Door Camera
- **RTSP URL:** rtsp://username:password@camera-ip:554/stream1
- **Enable Detection:** ✓

### Quick Start Script (Linux/Mac)

Create `start.sh` in project root:
```bash
#!/bin/bash

# Start Backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001 &
BACKEND_PID=$!

# Start Frontend
cd ../frontend
npm run dev &
FRONTEND_PID=$!

echo "✅ Chowkidar Started!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8001"
echo ""
echo "Press Ctrl+C to stop..."

# Wait and cleanup
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
```

```bash
chmod +x start.sh
./start.sh
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Database connection error | Check PostgreSQL is running: `docker ps` or `systemctl status postgresql` |
| Ollama not responding | Ensure Ollama is running: `ollama serve` |
| CUDA not available | Install NVIDIA drivers and CUDA toolkit |
| Port already in use | Change port: `--port 8002` for backend or `--port 3000` for frontend |
| CORS errors | Ensure `CORS_ORIGINS=*` in backend .env |

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

**Chowkidar** - Your AI-powered digital watchman 🛡️
