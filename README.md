# RealWorld FastAPI Backend

![CI/CD Pipeline](https://github.com/yourusername/realworld-fastapi/workflows/CI/CD%20Pipeline/badge.svg)
![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)
![FastAPI Version](https://img.shields.io/badge/fastapi-0.115+-green.svg)

Modern FastAPI implementation of the [RealWorld](https://github.com/gothinkster/realworld) backend spec.

## Features

- ✨ **FastAPI 0.115+** with async/await support
- 🗄️ **PostgreSQL 16** with SQLAlchemy 2.0
- 🔐 **JWT Authentication** with python-jose
- 📝 **Alembic** migrations
- 🐳 **Docker** & **Docker Compose** for local development
- 🧪 **pytest** with 80%+ coverage
- 🔍 **Ruff** for linting and formatting
- 🚀 **GitHub Actions** CI/CD pipeline
- 📦 **Redis** for caching

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- PostgreSQL 16 (or use Docker)

### Local Development with Docker

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/realworld-fastapi.git
   cd realworld-fastapi
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Start services**
   ```bash
   docker-compose up -d
   ```

4. **Access the API**
   - API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc
   - PGAdmin: http://localhost:5050 (use `--profile tools`)

### Local Development without Docker

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up database**
   ```bash
   # Create PostgreSQL database
   createdb realworld
   
   # Run migrations
   alembic upgrade head
   ```

3. **Run the application**
   ```bash
   uvicorn app.main:app --reload
   ```

## Testing

### Run all tests
```bash
pytest tests/ -v
```

### Run with coverage
```bash
pytest tests/ --cov=app --cov-report=html
```

### Run specific test file
```bash
pytest tests/test_auth.py -v
```

## Code Quality

### Linting
```bash
ruff check app/ tests/
```

### Formatting
```bash
ruff format app/ tests/
```

### Type checking
```bash
mypy app/
```

## Database Migrations

### Create a new migration
```bash
alembic revision --autogenerate -m "description"
```

### Apply migrations
```bash
alembic upgrade head
```

### Rollback migration
```bash
alembic downgrade -1
```

## API Documentation

Once the application is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration and settings
│   ├── database.py          # Database connection and session
│   ├── dependencies.py      # Shared dependencies
│   ├── auth/                # Authentication module
│   ├── articles/            # Articles module
│   ├── profiles/            # Profiles module
│   └── core/                # Core utilities
├── migrations/              # Alembic migrations
├── tests/                   # Test suite
├── docker-compose.yml       # Docker Compose configuration
├── Dockerfile               # Multi-stage Docker build
├── requirements.txt         # Python dependencies
└── alembic.ini             # Alembic configuration
```

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT secret key (generate with `openssl rand -hex 32`)
- `REDIS_URL`: Redis connection string
- `ALLOWED_ORIGINS`: CORS allowed origins

## CI/CD Pipeline

The GitHub Actions pipeline automatically:
1. ✅ Runs linting (Ruff)
2. ✅ Runs type checking (mypy)
3. ✅ Runs tests with PostgreSQL service
4. ✅ Generates coverage reports
5. ✅ Builds Docker image
6. ✅ Runs security scans (Bandit, Safety)

## Deployment

### Docker
```bash
docker build -t realworld-fastapi .
docker run -p 8000:8000 --env-file .env realworld-fastapi
```

### Production Considerations

- Use a production WSGI server (uvicorn with Gunicorn)
- Enable HTTPS/TLS
- Set `DEBUG=false`
- Use strong `SECRET_KEY`
- Configure proper CORS origins
- Set up database backups
- Enable monitoring and logging
- Use environment-specific configurations

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [RealWorld](https://github.com/gothinkster/realworld) for the API spec
- [FastAPI](https://fastapi.tiangolo.com/) framework
- [SQLAlchemy](https://www.sqlalchemy.org/) ORM