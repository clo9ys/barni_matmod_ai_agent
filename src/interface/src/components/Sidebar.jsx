import React, { useState, useEffect } from 'react';

export default function Sidebar({ token, onLogout }) {
    const [history, setHistory] = useState([]);

    useEffect(() => {
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
        fetchHistory();
    }, [token]);

    return (
        <aside className="sidebar">
            <div className="sidebar-header" style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                <h2 className="sidebar-title">НЦСЭД Ассистент</h2>
                <button onClick={onLogout} style={{background: 'transparent', color: '#ff4d4f', border: 'none', cursor: 'pointer'}}>Выйти</button>
            </div>
            <div className="sidebar-actions">
                <button className="btn-primary sidebar-btn">+ Новый запрос</button>
            </div>
            <div className="sidebar-history">
                <p>История исследований</p>
                <ul className="history-list">
                    {history.map((item) => (
                        <li key={item.id} className="history-item">
                            <span className="history-status">[{item.status}]</span>
                            <span className="history-query">{item.query}</span>
                        </li>
                    ))}
                </ul>
            </div>
        </aside>
    );
}