# Conduit API - FastAPI Implementation

A real-world FastAPI application implementing the [RealWorld](https://github.com/gothinkster/realworld) spec.

## Features

- 🚀 **FastAPI** - Modern, fast (high-performance) web framework
- 🗃️ **SQLAlchemy 2.0** - SQL toolkit and ORM
- 🔄 **Alembic** - Database migrations
- 🔐 **JWT Authentication** - Secure token-based auth
- 📦 **PostgreSQL** - Robust relational database
- ⚡ **Redis** - Fast caching layer
- 🐳 **Docker** - Containerized deployment
- ✅ **Pytest** - Comprehensive test suite
- 🔍 **Ruff** - Fast Python linter

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for local development)

### Run with Docker Compose

1. Clone the repository:
```bash
git clone <repository-url>
cd conduit-api
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Start all services:
```bash
docker-compose up -d
```

4. API will be available at `http://localhost:8000`
5. API documentation at `http://localhost:8000/docs`

### Local Development

1. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start PostgreSQL and Redis:
```bash
docker-compose up -d postgres redis
```

4. Run migrations:
```bash
alembic upgrade head
```

5. Start development server:
```bash
uvicorn app.main:app --reload
```

## Testing

Run the test suite:
```bash
pytest tests/ -v
```

With coverage:
```bash
pytest tests/ -v --cov=app --cov-report=html
```

## Code Quality

Run linter:
```bash
ruff check .
```

Format code:
```bash
ruff format .
```

## API Endpoints

### Authentication
- `POST /api/users` - Register
- `POST /api/users/login` - Login
- `GET /api/user` - Get current user
- `PUT /api/user` - Update user

### Profiles
- `GET /api/profiles/{username}` - Get profile
- `POST /api/profiles/{username}/follow` - Follow user
- `DELETE /api/profiles/{username}/follow` - Unfollow user

### Articles
- `GET /api/articles` - List articles
- `POST /api/articles` - Create article
- `GET /api/articles/{slug}` - Get article
- `PUT /api/articles/{slug}` - Update article
- `DELETE /api/articles/{slug}` - Delete article
- `POST /api/articles/{slug}/favorite` - Favorite article
- `DELETE /api/articles/{slug}/favorite` - Unfavorite article

### Comments
- `POST /api/articles/{slug}/comments` - Add comment
- `GET /api/articles/{slug}/comments` - List comments
- `DELETE /api/articles/{slug}/comments/{id}` - Delete comment

### Tags
- `GET /api/tags` - List tags

## Project Structure

```
.
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database connection
│   ├── auth/                # Authentication module
│   ├── articles/            # Articles module
│   ├── profiles/            # Profiles module
│   └── core/                # Core utilities
├── alembic/                 # Database migrations
├── tests/                   # Test suite
├── docker-compose.yml       # Docker services
├── Dockerfile              # Container definition
└── requirements.txt        # Python dependencies
```

## Environment Variables

See `.env.example` for all available configuration options.

## CI/CD

GitHub Actions pipeline includes:
- ✅ Linting with Ruff
- ✅ Tests with Pytest
- ✅ PostgreSQL service container
- ✅ Code coverage reporting
- ✅ Docker image build & push

## License

MIT