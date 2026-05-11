import React from 'react';
import ResearchDefinitionCard from './cards/ResearchDefinitionCard';
import HypothesisCard from './cards/HypothesisCard';
import SourceCard from './cards/SourceCard';
import PlanCard from './cards/PlanCard';
import ScriptCard from './cards/ScriptCard';
import ResultCard from './cards/ResultCard';

export default function ArtifactViewer({ step, data, query }) {
    const renderArtifact = () => {
        if (step === 0) {
            return (
                <div className="bg-white border border-soft-border rounded-2xl p-8 shadow-sm">
                    <h3 className="text-sm font-bold text-soft-accent uppercase tracking-wider mb-4">Ваш запрос:</h3>
                    <p className="text-xl font-medium leading-relaxed text-soft-text italic">
                        "{query || "Ожидание ввода..."}"
                    </p>
                </div>
            );
        }

        if (!data) return (
            <div className="flex flex-col items-center justify-center py-20 text-soft-muted">
                <div className="text-4xl mb-4 opacity-20">📂</div>
                <p className="text-sm font-medium">Данные для этого этапа еще не получены...</p>
            </div>
        );

        switch (step) {
            case 1: return <ResearchDefinitionCard data={data} />;
            case 2: return <SourceCard source={data} />;
            case 3: return <HypothesisCard hypotheses={data.hypotheses} />;
            case 4: return <PlanCard data={data} />;
            case 5: return <ScriptCard data={data} />;
            case 6: return <ResultCard data={data} />;
            default: return <p className="text-soft-muted text-center py-10">Результаты этапа {step} в обработке...</p>;
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between mb-8">
                <h2 className="text-2xl font-black tracking-tight text-soft-text">Результат этапа</h2>
                <span className="px-3 py-1 bg-soft-sidebar border border-soft-border rounded-full text-[10px] font-bold text-soft-muted uppercase">
                    Этап {step}
                </span>
            </div>
            {renderArtifact()}
        </div>
    );
}
