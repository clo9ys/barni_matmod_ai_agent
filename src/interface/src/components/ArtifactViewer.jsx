import React, { useState } from 'react';
import ResearchDefinitionCard from './cards/ResearchDefinitionCard';
import HypothesisCard from './cards/HypothesisCard';
import SourceCard from './cards/SourceCard';

export default function ArtifactViewer({ currentStep }) {
    // 1. Моковые данные для шага "Определение"
    const researchData = {
        geography: 'Страны БРИКС',
        timeframe: '2015-2024',
        perspective: 'Макроэкономика',
        questions: [
            'Как менялся ВВП?',
            'Какова динамика инфляции в сравнении с ЕС?'
        ]
    };

    // 2. Стейт и моки для шага "Дизайн" (с галочками)
    const [hypotheses, setHypotheses] = useState([
        { id: 1, title: 'ВВП стран стабильно рос после 2020 года', metrics: ['ВВП (млрд $)', 'Год к году (%)'], selected: true },
        { id: 2, title: 'Инфляция в РФ выше средней по группе', metrics: ['Индекс потребительских цен'], selected: false }
    ]);

    const toggleHypothesis = (id) => {
        setHypotheses(hypotheses.map(h =>
            h.id === id ? { ...h, selected: !h.selected } : h
        ));
    };

    // 3. Моковые данные для шага "План" (Источник)
    const sourceData = {
        title: 'World Bank Open Data',
        tags: ['API', 'JSON', 'Верифицировано'],
        description: 'Глобальная база данных Всемирного банка по макроэкономическим показателям.',
        organization: 'World Bank Group',
        url: 'https://data.worldbank.org/'
    };

    // Изолированная логика рендера без inline-стилей
    const renderArtifact = () => {
        switch (currentStep) {
            case 0:
                return <p>Опишите вашу задачу в чате слева.</p>;
            case 1:
                return <ResearchDefinitionCard data={researchData} />;
            case 2:
                return <HypothesisCard hypotheses={hypotheses} onToggle={toggleHypothesis} />;
            case 3:
                return (
                    <div>
                        <h3 className="section-subtitle">Структура целевого датасета</h3>
                        <table className="data-table">
                            <thead>
                            <tr><th>Измерение</th><th>Тип</th></tr>
                            </thead>
                            <tbody>
                            <tr><td>Страна</td><td>string</td></tr>
                            <tr><td>Год</td><td>int</td></tr>
                            <tr><td>ВВП</td><td>float</td></tr>
                            </tbody>
                        </table>
                    </div>
                );
            case 4:
                return (
                    <div>
                        <h3 className="section-subtitle">План сборки: Найденные источники</h3>
                        <SourceCard source={sourceData} />
                    </div>
                );
            case 5:
                return (
                    <div>
                        <h3 className="section-subtitle">Скрипт Python</h3>
                        <pre className="code-block">
{`import pandas as pd
import requests

def fetch_data():
    # Заглушка для генерации
    return pd.DataFrame()`}
            </pre>
                    </div>
                );
            case 6:
                return <div>Готовый датасет. [Скачать CSV]</div>;
            default:
                return null;
        }
    };

    return (
        <div>
            <h2 className="section-title">Результат этапа</h2>
            {renderArtifact()}
        </div>
    );
}