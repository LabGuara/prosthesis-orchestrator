from app.config import configure_logging, load_settings
from app.db import Database


if __name__ == "__main__":
    settings = load_settings()

    configure_logging(settings.log_level)

    db = Database(settings)
    db.connect()

    db.run_migrations()
