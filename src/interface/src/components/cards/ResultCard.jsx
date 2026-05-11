import React, { useState } from 'react';

export default function ResultCard({ data }) {
    const [imgErrors, setImgErrors] = useState({});

    if (!data) return (
        <div className="card border-dashed border-2 flex items-center justify-center py-12">
            <p className="text-soft-muted text-sm italic">Ожидание финальной сборки датасета...</p>
        </div>
    );

    const { message, file_url, plots = [], preview_columns = [], preview_rows = [] } = data;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="card border-soft-accent/30 bg-soft-accent/2 overflow-hidden">
                <div className="p-6 border-b border-soft-accent/10 flex items-center justify-between bg-soft-accent/3">
                    <h4 className="text-lg font-bold text-soft-accent">Финальный датасет готов</h4>
                    <span className="px-2 py-1 bg-soft-accent text-white text-[10px] font-black rounded uppercase">Success</span>
                </div>
                <div className="p-8">
                    <p className="text-soft-text mb-8 leading-relaxed">{message}</p>
                    {file_url && (
                        <a
                            href={`http://localhost:8000${file_url}`}
                            download
                            className="inline-flex items-center gap-3 px-8 py-4 bg-soft-accent text-white rounded-xl font-bold shadow-lg shadow-soft-accent/20 hover:bg-sky-600 hover:-translate-y-0.5 transition-all"
                        >
                            <span className="text-xl">📥</span>
                            Скачать CSV
                        </a>
                    )}
                </div>
            </div>

            {plots.filter(url => !imgErrors[url]).map((url, i) => (
                <div key={i} className="card">
                    <div className="card-header">
                        <h4 style={{ color: '#e0e0e0' }}>График {i + 1}</h4>
                    </div>
                    <div className="card-body" style={{ padding: '12px' }}>
                        <img
                            src={`http://localhost:8000${url}`}
                            alt={`График ${i + 1}`}
                            style={{ width: '100%', borderRadius: '6px', display: 'block' }}
                            onError={() => setImgErrors(prev => ({ ...prev, [url]: true }))}
                        />
                    </div>
                </div>
            ))}

            {preview_rows.length > 0 && (
                <div className="card">
                    <div className="card-header">
                        <h4 style={{ color: '#e0e0e0' }}>Предпросмотр данных</h4>
                    </div>
                    <div className="card-body" style={{ padding: '0', overflowX: 'auto' }}>
                        <table style={{
                            width: '100%',
                            borderCollapse: 'collapse',
                            fontSize: '12px',
                            fontFamily: 'monospace',
                        }}>
                            <thead>
                                <tr>
                                    {preview_columns.map(col => (
                                        <th key={col} style={{
                                            padding: '8px 12px',
                                            textAlign: 'left',
                                            borderBottom: '1px solid rgba(255,255,255,0.12)',
                                            color: '#deff9a',
                                            whiteSpace: 'nowrap',
                                            background: 'rgba(255,255,255,0.03)',
                                        }}>
                                            {col}
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody>
                                {preview_rows.map((row, ri) => (
                                    <tr key={ri} style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                                        {preview_columns.map(col => (
                                            <td key={col} style={{
                                                padding: '6px 12px',
                                                color: '#c8c8c8',
                                                whiteSpace: 'nowrap',
                                            }}>
                                                {row[col] ?? ''}
                                            </td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
}
