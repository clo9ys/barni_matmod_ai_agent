import React from 'react';

const STRATEGY_LABELS = {
    single_source: 'Один источник',
    concat_by_year: 'Объединение по годам',
    priority_merge: 'Приоритетное слияние',
    join: 'Join по ключу',
};

export default function PlanCard({ data }) {
    if (!data) return <p className="dimmed">Загрузка плана...</p>;

    const { combination_strategy, join_key, output_columns, sources = [] } = data;

    return (
        <div className="card">
            <h3 className="card-title">План сборки данных</h3>

            <div style={{ display: 'flex', gap: '24px', marginBottom: '16px', flexWrap: 'wrap' }}>
                {combination_strategy && (
                    <div>
                        <div style={{ fontSize: '11px', color: '#888', marginBottom: '4px', textTransform: 'uppercase' }}>Стратегия</div>
                        <div style={{ color: '#deff9a', fontWeight: 600 }}>
                            {STRATEGY_LABELS[combination_strategy] || combination_strategy}
                        </div>
                    </div>
                )}
                {join_key && (
                    <div>
                        <div style={{ fontSize: '11px', color: '#888', marginBottom: '4px', textTransform: 'uppercase' }}>Ключ объединения</div>
                        <div style={{ color: '#e0e0e0', fontFamily: 'monospace' }}>{join_key}</div>
                    </div>
                )}
            </div>

            {sources.length > 0 && (
                <div style={{ marginBottom: '16px' }}>
                    <div style={{ fontSize: '11px', color: '#888', marginBottom: '8px', textTransform: 'uppercase' }}>Источники данных</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {sources.map((src, i) => (
                            <div key={i} style={{
                                background: 'rgba(255,255,255,0.04)',
                                border: '1px solid rgba(255,255,255,0.1)',
                                borderRadius: '8px',
                                padding: '10px 14px',
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                                    <div>
                                        <div style={{ fontSize: '13px', color: '#deff9a', fontFamily: 'monospace', marginBottom: '4px' }}>
                                            {src.dataset_id}
                                        </div>
                                        {src.indicator && (
                                            <div style={{ fontSize: '13px', color: '#e0e0e0' }}>{src.indicator}</div>
                                        )}
                                    </div>
                                    {src.role && src.role !== 'primary' && (
                                        <span style={{
                                            fontSize: '11px',
                                            color: '#aaa',
                                            border: '1px solid rgba(255,255,255,0.15)',
                                            borderRadius: '4px',
                                            padding: '2px 7px',
                                            whiteSpace: 'nowrap',
                                        }}>
                                            {src.role}
                                        </span>
                                    )}
                                </div>
                                {src.years && (
                                    <div style={{ fontSize: '12px', color: '#888', marginTop: '6px' }}>
                                        Годы: {Array.isArray(src.years) ? `${src.years[0]}–${src.years[src.years.length - 1]} (${src.years.length} лет)` : src.years}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {output_columns && output_columns.length > 0 && (
                <div>
                    <div style={{ fontSize: '11px', color: '#888', marginBottom: '8px', textTransform: 'uppercase' }}>Итоговые колонки</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                        {output_columns.map((col, i) => (
                            <span key={i} style={{
                                background: 'rgba(222,255,154,0.1)',
                                border: '1px solid rgba(222,255,154,0.25)',
                                color: '#deff9a',
                                borderRadius: '5px',
                                padding: '3px 9px',
                                fontSize: '12px',
                                fontFamily: 'monospace',
                            }}>
                                {typeof col === 'object' ? (col.name || JSON.stringify(col)) : col}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
