import React from 'react';

export default function Chat() {
    return (
        <>
            <div className="messages-area">
                <div className="chat-placeholder">
                    <div className="chat-icon">🤖</div>
                    <h3 className="chat-title">Виртуальный специалист</h3>
                    <p className="chat-subtitle">
                        Опишите задачу, и я помогу спроектировать исследование.
                    </p>
                </div>
            </div>

            <div className="input-area">
                <textarea
                    rows="1"
                    placeholder="Например: Собери динамику инфляции по странам ЕС..."
                ></textarea>
                <button className="btn-primary">Отправить</button>
            </div>
        </>
    );
}