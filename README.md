# 🔍 Smart Log Analyzer

Intelligent log analysis and monitoring system - A production-ready log analysis platform built with Python and FastAPI.

## 📋 Features

### Core Features
- ✅ **Log File Upload**: Multiple file upload with drag & drop support
- 🔍 **Automatic Analysis**: Logs are automatically parsed and analyzed
- 📊 **Classification**: Classification by ERROR, WARNING, INFO, DEBUG levels
- 🔥 **Error Detection**: Detects frequently recurring errors
- 📈 **Visualization**: Analysis results with charts and statistics
- 🤖 **AI Integration**: Log comments and recommendations with OpenAI (optional)
- 💾 **Database**: Data storage with PostgreSQL
- 🐳 **Docker**: Easy setup with Docker and Docker Compose
- 📚 **API Documentation**: Interactive API documentation with Swagger UI

### Advanced Features
- 📡 **Real-time Streaming**: Live log monitoring via WebSocket
- 🔖 **Saved Searches**: Save frequently used searches
- ⭐ **Favorites**: Add important log files to favorites
- 🚨 **Alert System**: Email/Slack/webhook notifications for critical errors
- 💬 **Log Comments**: Add notes to log lines
- ⌨️ **Keyboard Shortcuts**: Shortcuts for quick access
- 📊 **Log Comparison**: Compare two log files
- 🔍 **Advanced Filtering**: Regex, date range, multi-condition filtering
- 🏷️ **Tags and Categories**: Add tags and categories to files
- 📦 **Bulk Operations**: Multiple file selection and bulk operations
- 📥 **Export**: Export in PDF, Excel, JSON, XML formats
- 📜 **Search History**: Save recent searches and quick access
- 📊 **Dashboard Widgets**: Customizable dashboard
- 🎨 **Log Coloring**: Syntax highlighting and log level-based coloring
- 🔍 **Pattern Detection**: Automatic pattern detection and grouping
- 📅 **Timeline View**: Log visualization on timeline
- 👥 **Multi-user Support**: User accounts and role-based access control
- 📊 **Log Aggregation**: Collect logs from multiple sources
- 🤖 **ML Anomaly Detection**: Anomaly detection with Machine Learning
- 🔗 **Log Correlation**: Relationship analysis between log files
- ⚡ **Performance Metrics**: Response time, throughput analysis
- 🔌 **Integrations**: Slack, Teams, Jira, Trello integrations
- 📱 **Responsive Design**: Mobile and tablet compatible design

## 🚀 Quick Start

### Running with Docker (Recommended)

1. Clone the repository:
```bash
git clone <repo-url>
cd smart-log-analyzer
```

2. Start with Docker Compose:
```bash
docker-compose up -d
```

3. Access the application:
- Web Interface: http://localhost:8000
- API Documentation: http://localhost:8000/api/docs

### Manual Installation

1. Install requirements:
```bash
pip install -r requirements.txt
```

2. Create PostgreSQL database:
```sql
CREATE DATABASE loganalyzer;
```

3. Create `.env` file:
```bash
cp env.example .env
# Edit the .env file
```

4. Run the application:
```bash
uvicorn app.main:app --reload
```

## 📁 Project Structure

```
smart-log-analyzer/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application main file
│   ├── database.py          # Database configuration
│   ├── models.py            # SQLAlchemy models (User, LogFile, Tag, Category, etc.)
│   ├── schemas.py           # Pydantic schemas
│   ├── auth.py              # JWT authentication utilities
│   ├── log_parser.py        # Log parsing module
│   ├── analyzer.py          # Log analysis module
│   ├── ai_service.py        # AI integration (optional)
│   ├── pattern_detection.py # Pattern detection module
│   ├── export.py            # PDF/Excel export module
│   ├── integrations.py      # Slack/Teams/Jira/Trello integrations
│   ├── cache.py             # Redis cache (optional)
│   ├── tasks.py             # Celery background tasks (optional)
│   ├── monitoring.py        # Prometheus metrics (optional)
│   ├── ml/                  # Machine Learning modules
│   │   └── anomaly_detection.py
│   └── api/                 # API endpoints
│       ├── auth.py          # Authentication endpoints
│       ├── logs.py          # Log upload endpoints
│       ├── analysis.py      # Analysis endpoints
│       ├── dashboard.py     # Dashboard endpoints
│       ├── stream.py        # WebSocket streaming
│       ├── alerts.py        # Alert management
│       ├── tags.py          # Tag and category management
│       ├── favorites.py     # Favorites management
│       ├── saved_searches.py # Saved searches
│       ├── search_history.py # Search history
│       ├── comments.py      # Log entry comments
│       ├── comparison.py    # Log comparison
│       ├── export.py        # Export endpoints
│       ├── aggregation.py   # Log aggregation
│       ├── correlation.py   # Log correlation
│       ├── performance.py   # Performance metrics
│       ├── integrations.py  # Integration endpoints
│       └── ml.py            # ML endpoints
├── static/
│   └── index.html           # Web interface (single-page application)
├── mobile/                  # React Native mobile app (optional)
├── uploads/                 # Uploaded log files
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose configuration
├── env.example             # Environment variables example
└── README.md
```

## 🔌 API Endpoints

### Authentication
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/auth/me` - Current user information
- `PUT /api/auth/profile` - Profile update

### Log Files
- `POST /api/logs/upload` - Upload log file (multiple file support)
- `GET /api/logs/` - List all log files (filtering, tags, categories)
- `GET /api/logs/{file_id}` - Get specific log file
- `DELETE /api/logs/{file_id}` - Delete log file
- `POST /api/logs/bulk-delete` - Bulk file deletion
- `POST /api/logs/bulk-export` - Bulk export

### Analysis
- `GET /api/analysis/{file_id}` - Get analysis results
- `GET /api/analysis/{file_id}/entries` - Get log entries
- `GET /api/analysis/{file_id}/errors` - Get only errors
- `GET /api/analysis/{file_id}/warnings` - Get only warnings
- `GET /api/analysis/{file_id}/patterns` - Pattern detection results
- `GET /api/analysis/{file_id}/timeline` - Timeline view

### Dashboard
- `GET /api/dashboard/stats` - General statistics

### Real-time Streaming
- `WS /api/ws/logs/{file_id}` - Live log streaming via WebSocket

### Alerts
- `GET /api/alerts/` - List alert rules
- `POST /api/alerts/` - Create new alert rule
- `DELETE /api/alerts/{alert_id}` - Delete alert rule

### Tags & Categories
- `GET /api/tags/` - List all tags
- `POST /api/tags/` - Create new tag
- `GET /api/categories/` - List all categories
- `POST /api/categories/` - Create new category

### Favorites & Saved Searches
- `GET /api/favorites/` - List favorite files
- `POST /api/favorites/` - Add to favorites
- `DELETE /api/favorites/{file_id}` - Remove from favorites
- `GET /api/saved-searches/` - List saved searches
- `POST /api/saved-searches/` - Save new search

### Export
- `GET /api/export/{file_id}/pdf` - PDF export
- `GET /api/export/{file_id}/excel` - Excel export
- `GET /api/export/{file_id}/json` - JSON export
- `GET /api/export/{file_id}/xml` - XML export

### ML & Analytics
- `GET /api/ml/{file_id}/anomalies` - Anomaly detection
- `GET /api/correlation/event-chain` - Log correlation
- `GET /api/performance/response-times` - Performance metrics
- `GET /api/aggregation/combined-logs` - Log aggregation

For detailed documentation of all endpoints: http://localhost:8000/api/docs

## 🛠️ Technologies

### Backend
- **Framework**: FastAPI, Python 3.11+
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Authentication**: JWT (python-jose, bcrypt)
- **Background Jobs**: Celery (optional)
- **Caching**: Redis (optional)
- **ML/AI**: scikit-learn, OpenAI API (optional)
- **Export**: ReportLab (PDF), openpyxl (Excel)
- **Monitoring**: Prometheus (optional)

### Frontend
- **Framework**: Vanilla JavaScript
- **Charts**: Chart.js
- **Styling**: CSS Variables (Dark/Light Mode)
- **Real-time**: WebSocket

### Infrastructure
- **Containerization**: Docker, Docker Compose
- **CI/CD**: GitHub Actions (optional)
- **Mobile**: React Native, Expo (optional)

## 📊 Log Format Support

The system supports the following log formats:
- ISO 8601 date formats (2024-01-15 10:30:45)
- Various log level formats (ERROR, WARNING, INFO, DEBUG)
- Customizable parsing rules

## 🤖 AI Integration

To use AI analysis:
1. Add your OpenAI API key to the `.env` file:
```
OPENAI_API_KEY=your_api_key_here
```

2. Check the "Analyze with AI" option when uploading logs.

## 🔧 Configuration

To create a `.env` file, copy the `env.example` file:
```bash
cp env.example .env
```

Required environment variables:
- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:password@localhost:5432/loganalyzer`)
- `OPENAI_API_KEY`: OpenAI API key (optional, for AI features)
- `SECRET_KEY`: Secret key for JWT tokens (must be changed in production)
- `REDIS_URL`: Redis connection URL (optional, for caching)
- `CELERY_BROKER_URL`: Celery broker URL (optional, for background jobs)

**⚠️ Important**: The `.env` file is in `.gitignore` and will not be pushed to GitHub. Keep your API keys secure!

## 🔐 Security

- `.env` file is in `.gitignore` and will not be committed
- Authentication with JWT tokens
- Password hashing with bcrypt
- Role-based access control (admin, user, viewer)
- API endpoints require authentication (except optional endpoints)

## 📝 License

This project is for example and educational purposes.

## 👨‍💻 Developer Notes

- Log parsing algorithms can be customized in `app/log_parser.py`
- New analysis metrics can be added to `app/analyzer.py`
- API endpoints are in modular structure in `app/api/` folder

## 🐛 Troubleshooting

**Database connection error:**
- If using Docker Compose, start all services with `docker-compose up -d`
- In manual installation, ensure PostgreSQL is running

**File upload error:**
- Ensure the `uploads/` directory has write permissions

**AI analysis not working:**
- Check that your OpenAI API key is valid
- The system works without API key, only AI features will be disabled
