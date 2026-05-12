import React, { useState } from 'react';

export default function Auth({ onLogin }) {
    const [isLoginMode, setIsLoginMode] = useState(true);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const loginUser = async (user, pass) => {
        const formData = new URLSearchParams();
        formData.append('username', user);
        formData.append('password', pass);

        const res = await fetch('http://localhost:8000/api/v1/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData.toString()
        });

        if (!res.ok) throw new Error('Неверный логин или пароль');

        const data = await res.json();
        onLogin(data.access_token);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (isLoginMode) {
                await loginUser(username, password);
            } else {
                const res = await fetch(`/api/v1/auth/register?username=${username}&password=${password}`, {
                    method: 'POST'
                });

                if (!res.ok) throw new Error('Пользователь уже существует');
                await loginUser(username, password);
            }
        } catch (err) {
            setError(err.message);
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-soft-bg p-4 font-sans text-soft-text">
            <div className="w-full max-w-md bg-white rounded-2xl shadow-xl shadow-soft-border border border-soft-border overflow-hidden">
                <div className="p-8 text-center bg-soft-sidebar/50 border-b border-soft-border">
                    <h1 className="text-3xl font-black tracking-tighter text-soft-accent mb-1">БАРНИ</h1>
                    <p className="text-soft-muted text-sm font-medium">Ассистент проектирования исследований</p>
                </div>
                
                <div className="p-8">
                    <h2 className="text-xl font-bold mb-6 text-center">
                        {isLoginMode ? 'Вход в систему' : 'Регистрация'}
                    </h2>

                    <form onSubmit={handleSubmit} className="space-y-4">
                        <div>
                            <input
                                type="text"
                                placeholder="Логин"
                                className="w-full px-4 py-3 bg-soft-bg border border-soft-border rounded-xl focus:ring-2 focus:ring-soft-accent/20 focus:border-soft-accent outline-none transition-all"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required
                            />
                        </div>
                        <div>
                            <input
                                type="password"
                                placeholder="Пароль"
                                className="w-full px-4 py-3 bg-soft-bg border border-soft-border rounded-xl focus:ring-2 focus:ring-soft-accent/20 focus:border-soft-accent outline-none transition-all"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required
                            />
                        </div>

                        {error && (
                            <div className="p-3 bg-red-50 text-red-500 text-xs font-semibold rounded-lg border border-red-100 animate-pulse">
                                ⚠️ {error}
                            </div>
                        )}

                        <button 
                            type="submit" 
                            className="w-full py-4 bg-soft-accent text-white font-bold rounded-xl shadow-lg shadow-soft-accent/20 hover:bg-sky-600 active:scale-[0.98] transition-all disabled:opacity-50"
                            disabled={loading}
                        >
                            {loading ? (
                                <span className="flex items-center justify-center gap-2">
                                    <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    Загрузка...
                                </span>
                            ) : (
                                isLoginMode ? 'Войти' : 'Создать аккаунт'
                            )}
                        </button>
                    </form>

                    <div className="mt-8 pt-6 border-t border-soft-border text-center">
                        <button 
                            type="button"
                            className="text-sm font-semibold text-soft-muted hover:text-soft-accent transition-colors"
                            onClick={() => {
                                setIsLoginMode(!isLoginMode);
                                setError('');
                            }}
                        >
                            {isLoginMode ? 'Нет аккаунта? Зарегистрируйтесь' : 'Уже есть аккаунт? Войти'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}