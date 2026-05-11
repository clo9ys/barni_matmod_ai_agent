import React, { useState } from 'react';

export default function Auth({ onLogin }) {
    const [isLoginMode, setIsLoginMode] = useState(true);
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    // Вспомогательная функция для логина, чтобы не дублировать код
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
        onLogin(data.access_token); // Передаем токен наверх в App.jsx
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            if (isLoginMode) {
                // Обычный вход
                await loginUser(username, password);
            } else {
                // Регистрация
                const res = await fetch(`http://localhost:8000/api/v1/auth/register?username=${username}&password=${password}`, {
                    method: 'POST'
                });

                if (!res.ok) throw new Error('Пользователь уже существует');

                // Если регистрация успешна (200 OK), сразу же логиним пользователя!
                await loginUser(username, password);
            }
        } catch (err) {
            setError(err.message);
            setLoading(false); // Выключаем загрузку только если была ошибка
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

                    {error && <div className="auth-error">{error}</div>}

                    <button type="submit" className="btn-primary auth-submit-btn" disabled={loading}>
                        {loading ? 'Загрузка...' : (isLoginMode ? 'Войти' : 'Зарегистрироваться')}
                    </button>
                </form>

                <p className="auth-switch" onClick={() => {
                    setIsLoginMode(!isLoginMode);
                    setError(''); // Очищаем ошибки при переключении режима
                }}>
                    {isLoginMode ? 'Нет аккаунта? Зарегистрируйтесь' : 'Уже есть аккаунт? Войти'}
                </p>
            </div>
        </div>
    );
}