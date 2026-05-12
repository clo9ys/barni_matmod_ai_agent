import React, { useState, useEffect, useImperativeHandle, forwardRef } from 'react';

const Sidebar = forwardRef(({ token, currentSessionId, onLogout, onHistoryClick, onNewChat }, ref) => {
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

    useImperativeHandle(ref, () => ({
        refreshHistory: fetchHistory
    }));

    const handleDelete = async (e, sessionId) => {
        e.stopPropagation(); // Чтобы не сработало нажатие на сам айтем
        if (!window.confirm("Удалить это исследование?")) return;

        try {
            const res = await fetch(`http://localhost:8000/api/v1/research/${sessionId}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${token}` }
            });
            if (res.ok) {
                fetchHistory(); // Обновляем список
                if (currentSessionId === sessionId) {
                    onNewChat(); // Если удалили текущий чат, сбрасываем экран
                }
            }
        } catch (err) {
            console.error("Failed to delete research", err);
        }
    };

    useEffect(() => {
        fetchHistory();
    }, [token]);

    return (
        <aside className="w-64 bg-soft-sidebar border-r border-soft-border flex flex-col shrink-0">
            <div className="p-6 border-b border-soft-border flex items-center gap-3">
                <span className="text-2xl">🤖</span>
                <h2 className="text-lg font-black tracking-tighter text-soft-accent">БАРНИ</h2>
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
                    {history.map((item) => {
                        const isActive = item.session_id === currentSessionId;
                        return (
                            <li
                                key={item.session_id}
                                className={`p-3 rounded-lg cursor-pointer transition-all border group relative pr-10 ${
                                    isActive 
                                    ? 'bg-white shadow-sm border-soft-border' 
                                    : 'hover:bg-white hover:shadow-sm border-transparent hover:border-soft-border'
                                }`}
                                onClick={() => onHistoryClick(item.session_id)}
                            >
                                <span className={`block text-[10px] font-bold mb-1 ${item.current_step === 6 ? 'text-green-500' : 'text-soft-accent'}`}>
                                    {item.current_step === 6 ? '✓ Завершено' : `ШАГ ${item.current_step}/6`}
                                </span>
                                <span className={`block text-sm truncate transition-colors ${
                                    isActive ? 'text-soft-accent font-medium' : 'text-soft-text group-hover:text-soft-accent'
                                }`}>
                                    {item.query}
                                </span>
                                
                                <button
                                    onClick={(e) => handleDelete(e, item.session_id)}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 p-2 text-soft-muted hover:text-red-500 opacity-0 group-hover:opacity-100 transition-all"
                                    title="Удалить"
                                >
                                    🗑️
                                </button>
                            </li>
                        );
                    })}
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
});

export default Sidebar;