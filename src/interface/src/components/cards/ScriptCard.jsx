import React from 'react';

export default function ScriptCard({ data }) {
    if (!data || !data.code) return (
        <div className="card border-dashed border-2 flex items-center justify-center py-12">
            <p className="text-soft-muted text-sm italic">Код еще не сгенерирован...</p>
        </div>
    );

    return (
        <div className="card p-0 overflow-hidden">
            <div className="px-6 py-4 border-b border-soft-border bg-soft-sidebar/30 flex items-center justify-between">
                <h4 className="text-sm font-bold text-soft-text uppercase tracking-tight">Скрипт сборки данных (Python)</h4>
                <button 
                    onClick={() => navigator.clipboard.writeText(data.code)}
                    className="text-[10px] font-bold text-soft-accent hover:underline uppercase"
                >
                    Копировать
                </button>
            </div>
            <div className="p-6 bg-slate-900">
                <pre className="text-xs font-mono text-slate-300 overflow-x-auto leading-relaxed scrollbar-thin scrollbar-thumb-slate-700">
                    <code>{data.code}</code>
                </pre>
            </div>
        </div>
    );
}