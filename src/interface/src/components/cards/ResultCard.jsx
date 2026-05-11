import React from 'react';

export default function ResultCard({ data }) {
    if (!data) return <p className="dimmed">Ожидание финальной сборки датасета...</p>;

    return (
        <div className="card" style={{ borderColor: '#deff9a' }}>
            <div className="card-header" style={{ borderBottom: '1px solid rgba(222, 255, 154, 0.2)' }}>
                <h4 style={{ color: '#deff9a' }}>Финальный датасет готов</h4>
            </div>
            <div className="card-body">
                <p>{data.message || "Скрипт выполнен успешно."}</p>
                {/* Здесь в будущем можно отрендерить таблицу или кнопку "Скачать CSV" */}
            </div>
        </div>
    );
}