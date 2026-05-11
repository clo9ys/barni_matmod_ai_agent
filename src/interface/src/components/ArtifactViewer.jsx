import React from 'react';
import ResearchDefinitionCard from './cards/ResearchDefinitionCard';
import HypothesisCard from './cards/HypothesisCard';
import SourceCard from './cards/SourceCard';

export default function ArtifactViewer({ currentStep, artifactData }) {
    const renderArtifact = () => {
        if (!artifactData && currentStep !== 0) return <p>Ожидание данных этапа...</p>;

        switch (currentStep) {
            case 0: return <p>Опишите задачу, чтобы начать.</p>;
            case 1:
                // Step 1: Определение (geography, timeframe, perspective, questions)
                return <ResearchDefinitionCard data={artifactData} />;
            case 2:
                // Step 2: Гипотезы (hypotheses: [{title, metrics}])
                return <HypothesisCard hypotheses={artifactData.hypotheses} />;
            case 4:
                // Step 4: Источники (title, tags, description, url)
                return <SourceCard source={artifactData} />;
            default:
                return <p>Шаг {currentStep} находится в обработке...</p>;
        }
    };

    return (
        <div className="artifact-container">
            <h2 className="section-title">Результат этапа</h2>
            {renderArtifact()}
        </div>
    );
}