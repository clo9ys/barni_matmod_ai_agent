import React from 'react';
import ResearchDefinitionCard from './cards/ResearchDefinitionCard';
import HypothesisCard from './cards/HypothesisCard';
import SourceCard from './cards/SourceCard';
import ScriptCard from './cards/ScriptCard';
import ResultCard from './cards/ResultCard';

export default function ArtifactViewer({ step, data, query }) {
    const renderArtifact = () => {
        // Шаг 0: Запрос
        if (step === 0) {
            return (
                <div style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px' }}>
                    <h3 style={{ marginBottom: '10px', color: '#deff9a' }}>Ваш запрос:</h3>
                    <p style={{ fontSize: '18px', lineHeight: '1.5' }}>{query || "Ожидание ввода..."}</p>
                </div>
            );
        }

        if (!data) return <p className="dimmed" style={{ marginTop: '20px' }}>Данные для этого этапа еще не получены...</p>;

        switch (step) {
            case 1: return <ResearchDefinitionCard data={data} />;
            case 2: return <SourceCard source={data} />;
            case 3: return <HypothesisCard hypotheses={data.hypotheses} />;
            case 4: return <p className="dimmed">План сборки данных успешно прошел валидацию.</p>;
            case 5: return <ScriptCard data={data} />;
            case 6: return <ResultCard data={data} />;
            default: return <p>Результаты этапа {step} в обработке...</p>;
        }
    };

    return (
        <div className="artifact-container" style={{ width: '100%', maxWidth: '800px', margin: '0 auto' }}>
            <h2 style={{ marginBottom: '25px', fontSize: '24px' }}>Результат этапа</h2>
            {renderArtifact()}
        </div>
    );
}