import React, { useState } from 'react';
import './styles.css';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import ArtifactViewer from './components/ArtifactViewer';
import TraceLog from './components/TraceLog';
import Stepper from './components/Stepper';
import Auth from './components/Auth';
import { useAssistant } from './hooks/useAssistant';

const STEPS = ['Запрос', 'Определение', 'Дизайн', 'Структура', 'План', 'Скрипт', 'Сборка'];

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('access_token'));

  const {
    currentStep, viewStep, setViewStep,
    logs, artifacts, isProcessing,
    initialQuery, sendMessage, loadResearch, resetAssistant
  } = useAssistant(token);

  if (!token) return <Auth onLogin={(t) => { localStorage.setItem('access_token', t); setToken(t); }} />;

  return (
      <div className="app-layout">
        <Sidebar
            token={token}
            onLogout={() => { localStorage.removeItem('access_token'); setToken(null); }}
            onHistoryClick={loadResearch}
            onNewChat={resetAssistant}
        />

        <div className="main-area">
          <header className="top-bar">
            <Stepper steps={STEPS} current={currentStep} selected={viewStep} onSelect={setViewStep} />
          </header>

          <div className="workspace">
            <section className="chat-panel">
              <Chat onSend={sendMessage} disabled={isProcessing} query={initialQuery} />
            </section>

            <section className="artifact-panel">
              <ArtifactViewer
                  step={viewStep}
                  data={artifacts[viewStep]}
                  query={initialQuery}
              />
            </section>
          </div>

          <footer className="trace-log">
            <TraceLog logs={logs} />
          </footer>
        </div>
      </div>
  );
}