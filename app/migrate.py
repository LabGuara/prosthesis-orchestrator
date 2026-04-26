from app.config import load_settings
from app.db import Database


if __name__ == "__main__":
    settings = load_settings()
    
    db = Database(settings)
    db.connect()
    
    db.run_migrations()