import React from 'react';

const STRATEGY_LABELS = {
    single_source: 'Один источник',
    concat_by_year: 'Объединение по годам',
    priority_merge: 'Приоритетное слияние',
    join: 'Join по ключу',
};

export default function PlanCard({ data }) {
    if (!data) return <p className="text-soft-muted text-sm">Загрузка плана...</p>;

    const { combination_strategy, join_key, output_columns, sources = [] } = data;

    return (
        <div className="card space-y-6">
            <h3 className="text-lg font-bold text-soft-text">План сборки данных</h3>

            <div className="flex gap-8 flex-wrap">
                {combination_strategy && (
                    <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-soft-muted mb-1">Стратегия</div>
                        <div className="text-sm font-semibold text-soft-accent">
                            {STRATEGY_LABELS[combination_strategy] || combination_strategy}
                        </div>
                    </div>
                )}
                {join_key && (
                    <div>
                        <div className="text-[10px] font-bold uppercase tracking-wider text-soft-muted mb-1">Ключ объединения</div>
                        <div className="text-sm font-mono text-soft-text">{join_key}</div>
                    </div>
                )}
            </div>

            {sources.length > 0 && (
                <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-soft-muted mb-3">Источники данных</div>
                    <div className="flex flex-col gap-2">
                        {sources.map((src, i) => (
                            <div key={i} className="bg-soft-bg border border-soft-border rounded-xl px-4 py-3">
                                <div className="flex justify-between items-start gap-3">
                                    <div>
                                        <div className="text-sm font-mono font-semibold text-soft-accent mb-1">
                                            {src.dataset_id}
                                        </div>
                                        {src.indicator && (
                                            <div className="text-sm text-soft-text">{src.indicator}</div>
                                        )}
                                    </div>
                                    {src.role && src.role !== 'primary' && (
                                        <span className="text-[11px] text-soft-muted border border-soft-border rounded px-2 py-0.5 whitespace-nowrap">
                                            {src.role}
                                        </span>
                                    )}
                                </div>
                                {src.years && (
                                    <div className="text-xs text-soft-muted mt-1.5">
                                        Годы: {Array.isArray(src.years)
                                            ? `${src.years[0]}–${src.years[src.years.length - 1]} (${src.years.length} лет)`
                                            : src.years}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {output_columns && output_columns.length > 0 && (
                <div>
                    <div className="text-[10px] font-bold uppercase tracking-wider text-soft-muted mb-3">Итоговые колонки</div>
                    <div className="flex flex-wrap gap-2">
                        {output_columns.map((col, i) => (
                            <span key={i} className="bg-soft-accent/10 border border-soft-accent/20 text-soft-accent rounded-md px-2.5 py-1 text-xs font-mono">
                                {typeof col === 'object' ? (col.name || JSON.stringify(col)) : col}
                            </span>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
