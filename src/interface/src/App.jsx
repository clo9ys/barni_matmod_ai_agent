import React, { useState, useEffect } from 'react';
import './styles.css';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import ArtifactViewer from './components/ArtifactViewer';
import TraceLog from './components/TraceLog';
import Stepper from './components/Stepper';
import Auth from './components/Auth'; // Импортируем компонент авторизации
import { useAssistant } from './hooks/useAssistant';

const STEPS = [
  'Запрос',
  'Определение',
  'Дизайн',
  'Структура',
  'План',
  'Скрипт',
  'Сборка'
];

export default function App() {
  const [token, setToken] = useState(null);

  // При первой загрузке проверяем, есть ли сохраненный токен
  useEffect(() => {
    const savedToken = localStorage.getItem('access_token');
    if (savedToken) {
      setToken(savedToken);
    }
  }, []);

  // Функция успешного входа
  const handleLogin = (newToken) => {
    localStorage.setItem('access_token', newToken);
    setToken(newToken);
  };

  // Функция выхода
  const handleLogout = () => {
    localStorage.removeItem('access_token');
    setToken(null);
  };

  // Передаем токен в хук!
  const { currentStep, setCurrentStep, logs, artifactData, isProcessing, sendMessage } = useAssistant(token);

  // Если токена нет, показываем только страницу авторизации
  if (!token) {
    return <Auth onLogin={handleLogin} />;
  }

  // Если токен есть, показываем основное приложение
  return (
      <div className="app-layout">
        {/* Передаем функцию логаута и токен в сайдбар */}
        <Sidebar onLogout={handleLogout} token={token} />

        <div className="main-area">
          <header className="top-bar">
            <Stepper steps={STEPS} current={currentStep} onSelect={setCurrentStep} />
          </header>

          <div className="workspace">
            <section className="chat-panel">
              <Chat onSend={sendMessage} disabled={isProcessing} />
            </section>

            <section className="artifact-panel">
              <ArtifactViewer currentStep={currentStep} artifactData={artifactData} />
            </section>
          </div>

          <footer className="trace-log">
            <TraceLog logs={logs} />
          </footer>
        </div>
      </div>
  );
}