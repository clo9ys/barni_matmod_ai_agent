import React from 'react';

export default function Sidebar() {
    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <h2 className="sidebar-title">НЦСЭД Ассистент</h2>
            </div>

            <div className="sidebar-actions">
                <button className="btn-primary sidebar-btn">
                    + Новый запрос
                </button>
            </div>

            <div className="sidebar-history">
                <p>Недавние</p>
                {/* Заглушки для истории будут здесь */}
            </div>
        </aside>
    );
}