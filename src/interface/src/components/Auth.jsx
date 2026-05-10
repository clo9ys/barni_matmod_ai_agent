import React, { useState } from 'react';

export default function Auth({ onLogin }) {
    const [isLoginMode, setIsLoginMode] = useState(true);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (isLoginMode) {
                // Логин (FastAPI OAuth2PasswordRequestForm ждет FormData)
                const formData = new URLSearchParams();
                formData.append('username', username);
                formData.append('password', password);

                const res = await fetch('http://localhost:8000/api/v1/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: formData.toString()
                });

                if (!res.ok) throw new Error('Неверный логин или пароль');

                const data = await res.json();
                onLogin(data.access_token); // Передаем токен наверх
            } else {
                // Регистрация (в твоем бэке она сделана через query параметры)
                const res = await fetch(`http://localhost:8000/api/v1/auth/register?username=${username}&password=${password}`, {
                    method: 'POST'
                });

                if (!res.ok) throw new Error('Пользователь уже существует');

                // Если регистрация успешна, сразу переключаем на форму входа
                setIsLoginMode(true);
                setError('Регистрация успешна! Теперь войдите.');
            }
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="auth-container">
            <div className="auth-card">
                <h2>{isLoginMode ? 'Вход в систему' : 'Регистрация'}</h2>
                <p className="auth-subtitle">ИИ-ассистент НЦСЭД</p>

                <form onSubmit={handleSubmit}>
                    <input
                        type="text"
                        placeholder="Логин"
                        value={username}
                        onChange={(e) => setUsername(e.target.value)}
                        required
                    />
                    <input
                        type="password"
                        placeholder="Пароль"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                    />

                    {error && <div className={`auth-error ${error.includes('успешна') ? 'success' : ''}`}>{error}</div>}

                    <button type="submit" className="btn-primary" disabled={loading}>
                        {loading ? 'Загрузка...' : (isLoginMode ? 'Войти' : 'Зарегистрироваться')}
                    </button>
                </form>

                <p className="auth-switch" onClick={() => setIsLoginMode(!isLoginMode)}>
                    {isLoginMode ? 'Нет аккаунта? Зарегистрируйтесь' : 'Уже есть аккаунт? Войти'}
                </p>
            </div>
        </div>
    );
}