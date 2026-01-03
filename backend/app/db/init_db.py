from app.db.session import engine
from app.db.models import Base
from app.db.models_intent import ExecutionIntent


def init_db():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    init_db()
    print("✅ Database tables created")
