from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel, create_engine, Session, Relationship, select
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "assistant.db"
sqlite_url = f"sqlite:///{DB_PATH}"

engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


class User(SQLModel, table=True):
    """таблица пользователей для авторизации"""
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # связь с исследованиями (история промптов)
    researches: List["ResearchTable"] = Relationship(back_populates="user")


class ResearchTable(SQLModel, table=True):
    """полная таблица состояния исследования (бывший researchstate)"""
    session_id: str = Field(primary_key=True)
    query: str = Field(nullable=False)
    current_step: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # связь с пользователем
    user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    user: Optional[User] = Relationship(back_populates="researches")

    # результаты шагов (храним как json-объекты)
    definition: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    design: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    structure: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    assembly_plan: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # дополнительные артефакты
    generated_script: Optional[str] = None
    final_dataset_url: Optional[str] = None

    # логирование "следа ассистента" и ошибок
    trace: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    errors: List[str] = Field(default_factory=list, sa_column=Column(JSON))


class DatasetTable(SQLModel, table=True):
    """таблица реестра для поиска по архиву"""
    id: str = Field(primary_key=True)
    title: str
    description: str
    source: str
    geography: str
    period: str
    columns: List[str] = Field(sa_column=Column(JSON))
    tags: List[str] = Field(sa_column=Column(JSON))
    file_path: str


def init_db():
    """создание всех таблиц при старте приложения"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)


def get_session():
    """генератор сессий для использования в fastapi Depends"""
    with Session(engine) as session:
        yield session
