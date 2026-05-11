import React from 'react';

export default function ResearchDefinitionCard({ data }) {
    if (!data) return null;

    const items = [
        { label: 'География', value: data.geography, icon: '🌍' },
        { label: 'Временные рамки', value: data.timeframe, icon: '📅' },
        { label: 'Ракурс', value: data.perspective, icon: '🔍' },
    ];

    return (
        <div className="card space-y-8">
            <h3 className="text-lg font-bold text-soft-text">Параметры исследования</h3>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {items.map((item, idx) => (
                    <div key={idx} className="space-y-2">
                        <div className="flex items-center gap-2 text-[10px] font-bold text-soft-muted uppercase tracking-wider">
                            <span>{item.icon}</span>
                            {item.label}
                        </div>
                        <div className="text-sm font-semibold text-soft-text bg-soft-bg p-3 rounded-xl border border-soft-border">
                            {item.value || 'Не задано'}
                        </div>
                    </div>
                ))}
            </div>

            <div className="pt-6 border-t border-soft-border">
                <span className="block mb-4 text-[10px] font-bold text-soft-muted uppercase tracking-wider">
                    Исследовательские вопросы:
                </span>
                <ul className="space-y-3">
                    {data.questions?.map((q, idx) => (
                        <li key={idx} className="flex gap-3 text-sm text-soft-text bg-white p-4 rounded-xl border border-soft-border shadow-sm">
                            <span className="text-soft-accent font-bold">?</span>
                            {q}
                        </li>
                    ))}
                </ul>
            </div>
        </div>
    );
}