from app.config import configure_logging, load_settings
from app.services.database_service import DatabaseService


if __name__ == "__main__":
    settings = load_settings()

    configure_logging(settings.log_level)

    db = DatabaseService(settings)
    db.connect()

    db.run_migrations()
