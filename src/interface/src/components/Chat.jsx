import React, { useState } from 'react';

export default function Chat({ onSend, disabled }) {
    const [inputValue, setInputValue] = useState('');

    const handleSubmit = (e) => {
        e.preventDefault();
        if (inputValue.trim() && !disabled) {
            onSend(inputValue);
            setInputValue(''); 
        }
    };

    return (
        <div className="flex-1 flex flex-col min-h-0 bg-white">
            <div className="flex-1 overflow-y-auto p-6 flex flex-col items-center justify-center text-center">
                <div className="max-w-md">
                    <div className="text-6xl mb-6 opacity-80">🤖</div>
                    <h3 className="text-2xl font-semibold mb-2 text-soft-text">Виртуальный специалист</h3>
                    <p className="text-soft-muted text-sm leading-relaxed">
                        Опишите задачу, и я помогу спроектировать исследование, собрать данные и подготовить аналитический скрипт.
                    </p>
                </div>
            </div>

            <form className="p-6 border-t border-soft-border bg-soft-sidebar/30" onSubmit={handleSubmit}>
                <div className="relative group">
                    <textarea
                        rows="3"
                        placeholder="Например: Собери динамику инфляции по странам ЕС за последние 5 лет..."
                        className="w-full bg-white border border-soft-border rounded-xl p-4 pr-32 text-sm focus:ring-2 focus:ring-soft-accent/20 focus:border-soft-accent outline-none transition-all resize-none shadow-sm"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        disabled={disabled}
                    />
                    <div className="absolute right-3 bottom-3">
                        <button
                            type="submit"
                            className="btn-primary flex items-center gap-2 text-sm font-semibold"
                            disabled={disabled}
                        >
                            {disabled ? (
                                <>
                                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    Думаю...
                                </>
                            ) : (
                                'Отправить'
                            )}
                        </button>
                    </div>
                </div>
            </form>
        </div>
    );
}