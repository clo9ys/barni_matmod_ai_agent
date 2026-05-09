import React from 'react';

export default function TraceLog() {
    return (
        <div>
            <p className="log-entry">&gt; Инициализация среды...</p>
            <p className="log-entry dimmed">&gt; Ожидание действий пользователя...</p>
        </div>
    );
}