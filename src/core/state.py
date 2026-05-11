from pydantic import BaseModel, Field
from typing import Optional


class ResearchDefinition(BaseModel):
    geography: Optional[str] = Field(description="Географический охват (страны, регионы). Null, если не указано.")
    timeframe: Optional[str] = Field(description="Временные рамки (годы, месяцы). Null, если не указано.")
    perspective: str = Field(description="Дисциплинарный ракурс (например: Макроэкономика, Демография).")
    questions: list[str] = Field(description="Список из 1-3 конкретных исследовательских вопросов.")

    # Флаги для контроля потока
    is_ambiguous: bool = Field(description="True, если запрос слишком общий и не хватает географии или времени.")
    clarifying_question: Optional[str] = Field(description="Короткий вопрос пользователю, если is_ambiguous = True.")


class ResearchDesign(BaseModel):
    """Шаг 3: Дизайн исследования"""
    hypotheses: list[str] = Field(..., description="Сформулированные гипотезы")
    indicators: list[str] = Field(..., description="Нужные измерения и индикаторы")
    grouping_methods: Optional[str] = Field(None, description="Методы группировки данных")


class DatasetAttribute(BaseModel):
    """Атрибут колонки датасета"""
    name: str
    data_type: str
    unit: Optional[str] = None


class DatasetStructure(BaseModel):
    """Шаг 4: Структура целевого датасета"""
    granularity: str = Field(..., description="Зернистость строк (например, 'страна-год')")
    attributes: list[DatasetAttribute] = Field(..., description="Список колонок датасета")


class DataSource(BaseModel):
    """Источник данных"""
    id: str
    title: str
    source_url: str
    relevance_score: float
    description: str


class AssemblyPlan(BaseModel):
    """Шаг 5: План сборки"""
    sources: list[DataSource]
    plan_description: str = Field(..., description="Как мы будем собирать данные из этих источников")


class ResearchState(BaseModel):
    """Общее состояние исследования (передается между шагами)"""
    session_id: str
    query: str = Field(..., description="Исходный запрос пользователя")

    # результаты шагов (заполняются по мере прохождения)
    definition: Optional[ResearchDefinition] = None
    design: Optional[ResearchDesign] = None
    structure: Optional[DatasetStructure] = None
    assembly_plan: Optional[AssemblyPlan] = None

    generated_script: Optional[str] = Field(None, description="Шаг 6: Сгенерированный Python/SQL скрипт")
    final_dataset_url: Optional[str] = Field(None, description="Шаг 7: Ссылка на итоговый файл")

    # след ассистента
    trace: list[str] = Field(default_factory=list, description="Логи действий системы")
    errors: list[str] = Field(default_factory=list)

    current_step: int = 1  # от 1 до 7

    def add_trace(self, message: str):
        self.trace.append(message)