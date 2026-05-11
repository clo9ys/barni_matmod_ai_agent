import React, { useEffect, useRef } from 'react';

export default function TraceLog({ logs }) {
    const endRef = useRef(null);

    // Автоматически скроллим вниз при появлении нового лога
    useEffect(() => {
        endRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [logs]);

    return (
        <div>
            {logs.map((log, index) => (
                <p key={index} className={`log-entry ${log.type === 'dimmed' ? 'dimmed' : ''}`}>
                    &gt; {log.text}
                </p>
            ))}
            <div ref={endRef} />
        </div>
    );
}