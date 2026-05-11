import React, { useState, useEffect } from 'react';
import ResearchDefinitionCard from './cards/ResearchDefinitionCard';
import HypothesisCard from './cards/HypothesisCard';
import SourceCard from './cards/SourceCard';
import PlanCard from './cards/PlanCard';
import ScriptCard from './cards/ScriptCard';
import ResultCard from './cards/ResultCard';

export default function ArtifactViewer({ step, data, query, onRefine, onConfirm, isRefining, awaitingConfirmation, canRefine }) {
    const [refineOpen, setRefineOpen] = useState(false);
    const [refineText, setRefineText] = useState('');

    useEffect(() => {
        setRefineOpen(false);
        setRefineText('');
    }, [step]);

    const handleRefineSubmit = () => {
        if (!refineText.trim() || !onRefine) return;
        onRefine(step, refineText.trim());
        setRefineOpen(false);
        setRefineText('');
    };

    const renderArtifact = () => {
        if (step === 0) {
            return (
                <div style={{ padding: '20px', background: 'rgba(255,255,255,0.02)', borderRadius: '12px' }}>
                    <h3 style={{ marginBottom: '10px', color: '#deff9a' }}>Ваш запрос:</h3>
                    <p style={{ fontSize: '18px', lineHeight: '1.5' }}>{query || 'Ожидание ввода...'}</p>
                </div>
            );
        }
        if (!data) return <p className="dimmed" style={{ marginTop: '20px' }}>Данные для этого этапа еще не получены...</p>;
        switch (step) {
            case 1: return <ResearchDefinitionCard data={data} />;
            case 2: return <SourceCard source={data} />;
            case 3: return <HypothesisCard data={data} />;
            case 4: return <PlanCard data={data} />;
            case 5: return <ScriptCard data={data} />;
            case 6: return <ResultCard data={data} />;
            default: return <p>Результаты этапа {step} в обработке...</p>;
        }
    };

    const showActions = canRefine;

    return (
        <div className="artifact-container" style={{ width: '100%', maxWidth: '800px', margin: '0 auto' }}>
            <h2 style={{ marginBottom: '25px', fontSize: '24px' }}>Результат этапа</h2>
            {renderArtifact()}

            {showActions && (
                <div style={{ marginTop: '16px', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '14px', display: 'flex', flexDirection: 'column', gap: '10px' }}>

                    {/* Confirm button — shown only when awaiting confirmation on this step */}
                    {awaitingConfirmation && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <button
                                onClick={onConfirm}
                                style={{
                                    background: '#deff9a',
                                    color: '#1a1a1a',
                                    border: 'none',
                                    padding: '8px 20px',
                                    borderRadius: '8px',
                                    cursor: 'pointer',
                                    fontSize: '14px',
                                    fontWeight: 700,
                                }}
                            >
                                Продолжить →
                            </button>
                            <span style={{ color: '#aaa', fontSize: '13px' }}>Проверьте результат шага и подтвердите</span>
                        </div>
                    )}

                    {/* Refine section */}
                    {!refineOpen ? (
                        <button
                            onClick={() => setRefineOpen(true)}
                            disabled={isRefining}
                            style={{
                                background: 'none',
                                border: '1px solid rgba(255,255,255,0.2)',
                                color: '#aaa',
                                padding: '5px 12px',
                                borderRadius: '6px',
                                cursor: isRefining ? 'not-allowed' : 'pointer',
                                fontSize: '13px',
                                width: 'fit-content',
                            }}
                        >
                            ✏️ Уточнить этот шаг
                        </button>
                    ) : (
                        <div>
                            <textarea
                                value={refineText}
                                onChange={e => setRefineText(e.target.value)}
                                placeholder="Опишите, что изменить или уточнить..."
                                rows={2}
                                disabled={isRefining}
                                style={{
                                    width: '100%',
                                    background: '#1e1e2e',
                                    border: '1px solid rgba(255,255,255,0.25)',
                                    color: '#e0e0e0',
                                    borderRadius: '6px',
                                    padding: '8px 10px',
                                    fontSize: '13px',
                                    resize: 'vertical',
                                    boxSizing: 'border-box',
                                    outline: 'none',
                                    fontFamily: 'inherit',
                                }}
                            />
                            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                                <button
                                    onClick={handleRefineSubmit}
                                    disabled={isRefining || !refineText.trim()}
                                    style={{
                                        background: '#deff9a',
                                        color: '#1a1a1a',
                                        border: 'none',
                                        padding: '6px 16px',
                                        borderRadius: '6px',
                                        cursor: (isRefining || !refineText.trim()) ? 'not-allowed' : 'pointer',
                                        fontSize: '13px',
                                        fontWeight: 600,
                                        opacity: isRefining ? 0.6 : 1,
                                    }}
                                >
                                    {isRefining ? 'Выполняется...' : 'Применить'}
                                </button>
                                <button
                                    onClick={() => { setRefineOpen(false); setRefineText(''); }}
                                    style={{
                                        background: 'none',
                                        border: '1px solid rgba(255,255,255,0.2)',
                                        color: '#aaa',
                                        padding: '6px 14px',
                                        borderRadius: '6px',
                                        cursor: 'pointer',
                                        fontSize: '13px',
                                    }}
                                >
                                    Отмена
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
