import React from 'react';

export default function HypothesisCard({ hypotheses, onToggle }) {
    if (!hypotheses || hypotheses.length === 0) return null;

    return (
        <div className="card">
            <h3 className="card-title">Проектирование исследования: Гипотезы</h3>
            <p className="card-description">
                Выберите гипотезы, которые нужно включить в итоговый датасет.
            </p>

            <div>
                {hypotheses.map((item) => (
                    <label key={item.id} className="checkbox-item">
                        <input
                            type="checkbox"
                            checked={item.selected}
                            onChange={() => onToggle && onToggle(item.id)}
                        />
                        <div className="checkbox-content">
                            <div className="checkbox-title">{item.title}</div>
                            <div className="checkbox-desc">
                                <strong>Метрики:</strong> {item.metrics.join(', ')}
                            </div>
                        </div>
                    </label>
                ))}
            </div>
        </div>
    );
}