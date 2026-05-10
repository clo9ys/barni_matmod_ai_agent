import React from 'react';
import ResearchDefinitionCard from './cards/ResearchDefinitionCard';
import HypothesisCard from './cards/HypothesisCard';
import SourceCard from './cards/SourceCard';

export default function ArtifactViewer({ step, data, query }) {
    const renderArtifact = () => {
        // Шаг 0: Показываем исходный запрос пользователя
        if (step === 0) {
            return (
                <div className="query-display">
                    <h3>Ваш запрос:</h3>
                    <p>{query || "Ожидание ввода..."}</p>
                </div>
            );
        }

        if (!data) return <p className="dimmed">Данные для этого этапа еще не получены...</p>;

        switch (step) {
            case 1: return <ResearchDefinitionCard data={data} />;
            case 2: return <HypothesisCard hypotheses={data.hypotheses} />;
            case 4: return <SourceCard source={data} />;
            default: return <p>Результаты этапа {step} в обработке...</p>;
        }
    };

    return (
        <div className="artifact-container">
            <h2 className="section-title">Результат этапа</h2>
            {renderArtifact()}
        </div>
    );
}