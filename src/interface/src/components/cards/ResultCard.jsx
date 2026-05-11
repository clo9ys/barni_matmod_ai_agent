import React, { useState } from 'react';

export default function ResultCard({ data }) {
    const [imgErrors, setImgErrors] = useState({});

    if (!data) return <p className="dimmed">Ожидание финальной сборки датасета...</p>;

    const { message, file_url, plots = [], preview_columns = [], preview_rows = [] } = data;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Header + download */}
            <div className="card" style={{ borderColor: '#deff9a' }}>
                <div className="card-header" style={{ borderBottom: '1px solid rgba(222, 255, 154, 0.2)' }}>
                    <h4 style={{ color: '#deff9a' }}>Финальный датасет готов</h4>
                </div>
                <div className="card-body">
                    <p>{message}</p>
                    {file_url && (
                        <a
                            href={`http://localhost:8000${file_url}`}
                            download
                            style={{
                                display: 'inline-block',
                                marginTop: '12px',
                                padding: '10px 20px',
                                background: '#deff9a',
                                color: '#121212',
                                textDecoration: 'none',
                                borderRadius: '8px',
                                fontWeight: 'bold',
                            }}
                        >
                            Скачать CSV
                        </a>
                    )}
                </div>
            </div>

            {/* Plots */}
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

            {/* Table preview */}
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
