import React from 'react';

export default function ResultCard({ data }) {
    if (!data) return (
        <div className="card border-dashed border-2 flex items-center justify-center py-12">
            <p className="text-soft-muted text-sm italic">Ожидание финальной сборки датасета...</p>
        </div>
    );

    return (
        <div className="card border-soft-accent/30 bg-soft-accent/2 overflow-hidden">
            <div className="p-6 border-b border-soft-accent/10 flex items-center justify-between bg-soft-accent/3">
                <h4 className="text-lg font-bold text-soft-accent">Финальный датасет готов</h4>
                <span className="px-2 py-1 bg-soft-accent text-white text-[10px] font-black rounded uppercase">Success</span>
            </div>
            <div className="p-8">
                <p className="text-soft-text mb-8 leading-relaxed">{data.message}</p>

                {data.file_url && (
                    <a
                        href={`http://localhost:8000${data.file_url}`}
                        download
                        className="inline-flex items-center gap-3 px-8 py-4 bg-soft-accent text-white rounded-xl font-bold shadow-lg shadow-soft-accent/20 hover:bg-sky-600 hover:-translate-y-0.5 transition-all"
                    >
                        <span className="text-xl">📥</span>
                        Скачать CSV
                    </a>
                )}
            </div>
        </div>
    );
}