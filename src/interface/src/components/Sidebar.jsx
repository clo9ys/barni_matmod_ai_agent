import React, { useState, useEffect } from 'react';

export default function Sidebar() {
    const [history, setHistory] = useState([]);
    const token = "your_access_token";

    useEffect(() => {
        const fetchHistory = async () => {
            try {
                const res = await fetch('http://localhost:8000/api/history', {
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
            <div className="sidebar-header">
                <h2 className="sidebar-title">НЦСЭД Ассистент</h2>
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