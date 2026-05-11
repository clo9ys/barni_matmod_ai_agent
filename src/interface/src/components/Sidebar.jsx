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
        <aside className="sidebar">
            <div className="sidebar-header" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                <h2 className="sidebar-title">БАРНИ</h2>
                <button onClick={onLogout} style={{background: 'transparent', color: '#ff4d4f', border: 'none', cursor: 'pointer'}}>Выйти</button>
            </div>
            <div className="sidebar-actions">
                <button onClick={onNewChat} className="btn-primary sidebar-btn">+ Новый запрос</button>
            </div>
            <div className="sidebar-history">
                <p style={{marginBottom: "10px", fontSize: "0.9rem", color: "#888"}}>История исследований</p>
                <ul className="history-list">
                    {history.map((item) => (
                        <li
                            key={item.session_id}
                            className="history-item"
                            onClick={() => onHistoryClick(item.session_id)}
                        >
                            <span className="history-status">[{item.current_step}/7]</span>
                            <span className="history-query">{item.query}</span>
                        </li>
                    ))}
                </ul>
            </div>
        </aside>
    );
}