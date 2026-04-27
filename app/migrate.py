from app.settings import Settings
from app.services.database_service import DatabaseService
from app.utils import configure_logging


if __name__ == "__main__":
    settings = Settings()

    configure_logging(settings.log_level)

    database_service = DatabaseService(settings)
    database_service.connect()

    database_service.run_migrations()
