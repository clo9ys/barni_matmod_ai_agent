import React from 'react';

export default function SourceCard({ source }) {
    if (!source) return null;

    return (
        <div className="card space-y-6">
            <h3 className="text-xl font-bold text-soft-text tracking-tight">{source.title}</h3>

            <div className="flex flex-wrap gap-2">
                {source.tags?.map((tag, idx) => (
                    <span key={idx} className="px-3 py-1 bg-soft-accent/10 text-soft-accent rounded-full text-[10px] font-bold uppercase tracking-wider">
                        {tag}
                    </span>
                ))}
            </div>

            <p className="text-sm text-soft-text leading-relaxed opacity-80">{source.description}</p>

            <div className="pt-6 border-t border-soft-border flex justify-between items-center">
                <div className="text-xs font-medium text-soft-muted italic">
                    Организация: <span className="text-soft-text not-italic font-bold">{source.organization}</span>
                </div>
                <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-bold text-soft-accent hover:underline flex items-center gap-1"
                >
                    Перейти к источнику
                    <span className="text-xs text-soft-muted group-hover:translate-x-1 transition-transform">↗</span>
                </a>
            </div>
        </div>
    );
}