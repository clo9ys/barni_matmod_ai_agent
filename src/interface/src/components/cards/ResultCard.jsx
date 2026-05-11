import React from 'react';

export default function ResultCard({ data }) {
    if (!data) return <p className="dimmed">Ожидание финальной сборки датасета...</p>;

    return (
        <div className="card" style={{ borderColor: '#deff9a' }}>
            <div className="card-header" style={{ borderBottom: '1px solid rgba(222, 255, 154, 0.2)' }}>
                <h4 style={{ color: '#deff9a' }}>Финальный датасет готов</h4>
            </div>
            <div className="card-body">
                <p>{data.message}</p>

                {data.file_url && (
                    <a
                        href={`http://localhost:8000${data.file_url}`}
                        download
                        style={{
                            display: 'inline-block',
                            marginTop: '15px',
                            padding: '10px 20px',
                            background: '#deff9a',
                            color: '#121212',
                            textDecoration: 'none',
                            borderRadius: '8px',
                            fontWeight: 'bold'
                        }}
                    >
                        📥 Скачать CSV
                    </a>
                )}
            </div>
        </div>
    );
}