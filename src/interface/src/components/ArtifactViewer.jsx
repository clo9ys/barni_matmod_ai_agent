import React from 'react';
import ResearchDefinitionCard from './cards/ResearchDefinitionCard';
import HypothesisCard from './cards/HypothesisCard';
import SourceCard from './cards/SourceCard';

export default function ArtifactViewer({ currentStep, artifactData }) {
    const renderArtifact = () => {
        switch (currentStep) {
            case 0:
                return <p>Опишите вашу задачу в чате слева.</p>;
            case 1:
                // Передаем реальные данные с бэкенда в карточку
                return <ResearchDefinitionCard data={artifactData} />;
            case 2:
                return <HypothesisCard hypotheses={artifactData?.hypotheses} />;
            case 3:
                return <div>Структура датасета...</div>;
            case 4:
                return <SourceCard source={artifactData} />;
            case 5:
                return <div>Скрипт Python...</div>;
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