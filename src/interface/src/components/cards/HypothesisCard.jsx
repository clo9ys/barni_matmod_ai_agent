import React, { useState, useEffect } from 'react';

export default function HypothesisCard({ data }) {
    const [hypotheses, setHypotheses] = useState([]);

    useEffect(() => {
        setHypotheses(data?.hypotheses || []);
    }, [data]);

    const toggle = (id) => {
        setHypotheses(prev =>
            prev.map(h => h.id === id ? { ...h, selected: !h.selected } : h)
        );
    };

    if (!hypotheses.length) return null;

    return (
        <div className="card">
            <h3 className="card-title">Проектирование исследования: Гипотезы</h3>
            <p className="card-description">
                Выберите гипотезы, которые нужно включить в итоговый датасет.
            </p>

            <div>
                {hypotheses.map((item) => (
                    <label key={item.id} className="checkbox-item" style={{ cursor: 'pointer' }}>
                        <input
                            type="checkbox"
                            checked={!!item.selected}
                            onChange={() => toggle(item.id)}
                        />
                        <div className="checkbox-content">
                            <div className="checkbox-title">{item.title}</div>
                            <div className="checkbox-desc">
                                <strong>Метрики:</strong> {item.metrics?.join(', ')}
                            </div>
                        </div>
                    </label>
                ))}
            </div>
        </div>
    );
}
