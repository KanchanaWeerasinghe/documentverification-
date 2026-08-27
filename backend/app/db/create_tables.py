from sqlalchemy import text

from backend.app.db.session import engine, Base
from backend.app.db import models  # ensure models are imported so Base.metadata has them


def create_all():
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=connection)


if __name__ == "__main__":
    create_all()
    print("Database tables created")
