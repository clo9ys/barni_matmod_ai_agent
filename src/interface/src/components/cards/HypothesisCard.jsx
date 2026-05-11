import React from 'react';

export default function HypothesisCard({ hypotheses, onToggle }) {
    if (!hypotheses || hypotheses.length === 0) return null;

    return (
        <div className="card space-y-6">
            <div>
                <h3 className="text-lg font-bold text-soft-text mb-1">Проектирование исследования: Гипотезы</h3>
                <p className="text-sm text-soft-muted">
                    Выберите гипотезы, которые нужно включить в итоговый датасет.
                </p>
            </div>

            <div className="space-y-3">
                {hypotheses.map((item) => (
                    <label 
                        key={item.id} 
                        className={`
                            flex gap-4 p-4 rounded-xl border transition-all cursor-pointer group
                            ${item.selected ? 'bg-soft-accent/5 border-soft-accent/30' : 'bg-white border-soft-border hover:border-soft-muted'}
                        `}
                    >
                        <div className="relative flex items-center">
                            <input
                                type="checkbox"
                                className="peer h-5 w-5 cursor-pointer appearance-none rounded-md border border-soft-border transition-all checked:bg-soft-accent checked:border-soft-accent"
                                checked={item.selected}
                                onChange={() => onToggle && onToggle(item.id)}
                            />
                            <span className="absolute text-white opacity-0 peer-checked:opacity-100 top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 pointer-events-none">
                                <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5" viewBox="0 0 20 20" fill="currentColor" stroke="currentColor" strokeWidth="1">
                                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd"></path>
                                </svg>
                            </span>
                        </div>
                        <div className="flex-1">
                            <div className={`font-semibold text-sm transition-colors ${item.selected ? 'text-soft-accent' : 'text-soft-text'}`}>
                                {item.title}
                            </div>
                            <div className="text-xs text-soft-muted mt-1">
                                <span className="font-bold uppercase tracking-wider text-[10px] mr-1">Метрики:</span> {item.metrics.join(', ')}
                            </div>
                        </div>
                    </label>
                ))}
            </div>
        </div>
    );
}