import React from 'react';

export default function SourceCard({ source }) {
    if (!source) return null;

    return (
        <div className="card">
            <h3 className="source-title">{source.title}</h3>

            <div className="tags-container">
                {source.tags?.map((tag, idx) => (
                    <span key={idx} className="badge">{tag}</span>
                ))}
            </div>

            <p className="source-desc">{source.description}</p>

            <div className="source-footer">
                <div className="source-org">
                    Организация: {source.organization}
                </div>
                <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="source-link"
                >
                    Перейти к источнику ↗
                </a>
            </div>
        </div>
    );
}