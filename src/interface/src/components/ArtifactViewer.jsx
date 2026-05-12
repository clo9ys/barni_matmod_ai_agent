import React, { useState, useEffect } from 'react';
import ResearchDefinitionCard from './cards/ResearchDefinitionCard';
import HypothesisCard from './cards/HypothesisCard';
import SourceCard from './cards/SourceCard';
import PlanCard from './cards/PlanCard';
import ScriptCard from './cards/ScriptCard';
import ResultCard from './cards/ResultCard';

function ClarificationForm({ questions, onSubmit }) {
    const [answers, setAnswers] = useState(() => Object.fromEntries(questions.map((_, i) => [i, ''])));

    useEffect(() => {
        setAnswers(Object.fromEntries(questions.map((_, i) => [i, ''])));
    }, [questions]);

    const allFilled = questions.every((_, i) => answers[i]?.trim());

    const handleSubmit = () => {
        const combined = questions
            .map((q, i) => `${q}: ${answers[i].trim()}`)
            .join('\n');
        onSubmit(combined);
    };

    return (
        <div className="bg-white border border-amber-300 rounded-2xl p-6 shadow-sm space-y-4">
            <h3 className="text-sm font-bold text-amber-600 uppercase tracking-wider">Уточните запрос</h3>
            {questions.map((q, i) => (
                <div key={i} className="space-y-1">
                    <label className="text-sm font-medium text-soft-text">{q}</label>
                    <input
                        type="text"
                        value={answers[i]}
                        onChange={e => setAnswers(prev => ({ ...prev, [i]: e.target.value }))}
                        onKeyDown={e => { if (e.key === 'Enter' && allFilled) handleSubmit(); }}
                        className="w-full border border-soft-border rounded-lg px-3 py-2 text-sm bg-soft-bg focus:outline-none focus:ring-2 focus:ring-amber-400/30 focus:border-amber-400"
                        placeholder="Ваш ответ..."
                    />
                </div>
            ))}
            <button
                onClick={handleSubmit}
                disabled={!allFilled}
                className="mt-2 px-6 py-2 bg-amber-400 text-white rounded-lg text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed hover:bg-amber-500 transition-colors"
            >
                Продолжить →
            </button>
        </div>
    );
}

export default function ArtifactViewer({ step, data, query, awaitingClarification, onClarify }) {
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

    const questions = step === 1 && awaitingClarification ? (data?.questions ?? []) : [];

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between mb-8">
                <h2 className="text-2xl font-black tracking-tight text-soft-text">Результат этапа</h2>
                <span className="px-3 py-1 bg-soft-sidebar border border-soft-border rounded-full text-[10px] font-bold text-soft-muted uppercase">
                    Этап {step}
                </span>
            </div>
            {renderArtifact()}
            {questions.length > 0 && (
                <ClarificationForm questions={questions} onSubmit={onClarify} />
            )}
        </div>
    );
}
