import React, { useEffect, useRef } from 'react';

export default function TraceLog({ logs }) {
    const endRef = useRef(null);

    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    return (
        <div className="space-y-1">
            {logs.map((log, index) => (
                <p key={index} className={`
                    leading-relaxed
                    ${log.type === 'dimmed' ? 'text-slate-500' : 
                      log.type === 'error' ? 'text-red-400' : 'text-sky-400'}
                `}>
                    <span className="opacity-50 mr-2">❯</span>
                    {log.text}
                </p>
            ))}
            <div ref={endRef} />
        </div>
    );
}