import React, { useState } from 'react';

export default function Chat({ onSend, disabled }) {
    const [inputValue, setInputValue] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (inputValue.trim() && !disabled) {
            onSend(inputValue);
            setInputValue(''); // Очищаем поле после отправки
        }
    };

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
                {/* В будущем здесь можно рендерить историю сообщений */}
            </div>

            <form className="input-area" onSubmit={handleSubmit}>
                <textarea
                    rows="2"
                    placeholder="Например: Собери динамику инфляции по странам ЕС..."
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    disabled={disabled}
                />
                <button
                    type="submit"
                    className="btn-primary"
                    disabled={disabled}
                >
                    {disabled ? 'Думаю...' : 'Отправить'}
                </button>
            </form>
        </>
    );
}