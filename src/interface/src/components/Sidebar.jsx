import React, { useState, useEffect } from 'react';

export default function Sidebar({ token, onLogout, onHistoryClick, onNewChat }) {
    const [history, setHistory] = useState([]);

    const fetchHistory = async () => {
        try {
            const res = await fetch('http://localhost:8000/api/v1/history', {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                const data = await res.json();
                setHistory(data);
            }
        } catch (err) {
            console.error("Failed to load history", err);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, [token]);

    return (
        <aside className="w-64 bg-soft-sidebar border-r border-soft-border flex flex-col shrink-0">
            <div className="p-6 border-b border-soft-border">
                <h2 className="text-lg font-bold tracking-tight text-soft-text">БАРНИ</h2>
            </div>
            
            <div className="p-4">
                <button 
                    onClick={onNewChat} 
                    className="w-full btn-primary shadow-sm"
                >
                    + Новый запрос
                </button>
            </div>
            
            <div className="flex-1 overflow-y-auto px-4 pb-4">
                <p className="px-2 mb-3 text-[10px] uppercase font-bold tracking-wider text-soft-muted">
                    История исследований
                </p>
                <ul className="space-y-1">
                    {history.map((item) => (
                        <li
                            key={item.session_id}
                            className="p-3 rounded-lg hover:bg-white hover:shadow-sm cursor-pointer transition-all border border-transparent hover:border-soft-border group"
                            onClick={() => onHistoryClick(item.session_id)}
                        >
                            <span className="block text-[10px] font-bold text-soft-accent mb-1">
                                ШАГ {item.current_step}/7
                            </span>
                            <span className="block text-sm text-soft-text truncate group-hover:text-soft-accent transition-colors">
                                {item.query}
                            </span>
                        </li>
                    ))}
                </ul>
            </div>

            <div className="p-4 border-t border-soft-border">
                <button 
                    onClick={onLogout} 
                    className="w-full px-4 py-2 text-sm font-semibold text-red-500 hover:bg-red-50 rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                    Выйти
                </button>
            </div>
        </aside>
    );
}