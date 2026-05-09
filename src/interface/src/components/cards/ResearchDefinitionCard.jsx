import React from 'react';

export default function ResearchDefinitionCard({ data }) {
    if (!data) return null;

    return (
        <div className="card">
            <h3 className="card-title">Параметры исследования</h3>

            <div className="param-group">
                <span className="param-label">География:</span>
                <span className="param-value">{data.geography || 'Не задано'}</span>
            </div>

            <div className="param-group">
                <span className="param-label">Временные рамки:</span>
                <span className="param-value">{data.timeframe || 'Не задано'}</span>
            </div>

            <div className="param-group">
                <span className="param-label">Ракурс:</span>
                <span className="param-value">{data.perspective || 'Не задано'}</span>
            </div>

            <div className="param-questions-group">
                <span className="param-questions-label">Исследовательские вопросы:</span>
                <ul className="questions-list">
                    {data.questions?.map((q, idx) => (
                        <li key={idx} className="question-item">{q}</li>
                    ))}
                </ul>
            </div>
        </div>
    );
}