import React from 'react';

export default function ScriptCard({ data }) {
    if (!data || !data.code) return <p className="dimmed">Код еще не сгенерирован...</p>;

    return (
        <div className="card">
            <div className="card-header">
                <h4>Скрипт сборки данных (Python)</h4>
            </div>
            <div className="card-body">
                <pre style={{
                    background: '#1a1a1a',
                    padding: '15px',
                    borderRadius: '8px',
                    overflowX: 'auto',
                    color: '#e2e8f0',
                    fontFamily: 'monospace',
                    fontSize: '14px',
                    border: '1px solid rgba(222, 255, 154, 0.2)'
                }}>
                    <code>{data.code}</code>
                </pre>
            </div>
        </div>
    );
}