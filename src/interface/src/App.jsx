import React, { useState } from 'react';
import './styles.css';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import ArtifactViewer from './components/ArtifactViewer';
import TraceLog from './components/TraceLog';
import Stepper from './components/Stepper';
import Auth from './components/Auth';
import { useAssistant } from './hooks/useAssistant';

const STEPS = ['Запрос', 'Определение', 'Источники', 'Гипотезы', 'План', 'Скрипт', 'Сборка'];

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('access_token'));

  const {
    currentStep, viewStep, setViewStep,
    logs, artifacts, isProcessing,
    initialQuery, sendMessage, loadResearch, resetAssistant
  } = useAssistant(token);

  if (!token) return <Auth onLogin={(t) => { localStorage.setItem('access_token', t); setToken(t); }} />;

  return (
      <div className="flex h-screen overflow-hidden bg-soft-bg text-soft-text">
        <Sidebar
            token={token}
            onLogout={() => { localStorage.removeItem('access_token'); setToken(null); }}
            onHistoryClick={loadResearch}
            onNewChat={resetAssistant}
        />

        <div className="flex-1 flex flex-col min-w-0">
          <header className="h-16 bg-white border-b border-soft-border flex items-center px-6 shrink-0">
            <Stepper steps={STEPS} current={currentStep} selected={viewStep} onSelect={setViewStep} />
          </header>

          <div className="flex-1 flex overflow-hidden">
            <section className="flex-1 flex flex-col border-r border-soft-border bg-white">
              <Chat onSend={sendMessage} disabled={isProcessing} query={initialQuery} />
            </section>

            <section className="flex-1 overflow-y-auto p-8 bg-soft-bg">
              <ArtifactViewer
                  step={viewStep}
                  data={artifacts[viewStep]}
                  query={initialQuery}
              />
            </section>
          </div>

          <footer className="h-40 bg-slate-900 text-sky-400 font-mono p-4 overflow-y-auto border-t border-slate-800 shrink-0 text-sm">
            <TraceLog logs={logs} />
          </footer>
        </div>
      </div>
  );
}