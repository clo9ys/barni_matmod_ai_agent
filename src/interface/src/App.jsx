import React, { useState, useRef } from 'react';
import './styles.css';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import ArtifactViewer from './components/ArtifactViewer';
import Stepper from './components/Stepper';
import Auth from './components/Auth';
import { useAssistant } from './hooks/useAssistant';

const STEPS = ['Запрос', 'Определение', 'Источники', 'Гипотезы', 'План', 'Скрипт', 'Результаты'];

export default function App() {
  const [token, setToken] = useState(localStorage.getItem('access_token'));
  const [inputValue, setInputValue] = useState('');
  const sidebarRef = useRef(null);

  const {
    currentSessionId,
    currentStep, viewStep, setViewStep,
    logs, artifacts, isProcessing, awaitingClarification,
    initialQuery, sendMessage, sendClarification, loadResearch, resetAssistant
  } = useAssistant(token, () => {
    sidebarRef.current?.refreshHistory();
  });

  if (!token) return <Auth onLogin={(t) => { localStorage.setItem('access_token', t); setToken(t); }} />;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isProcessing || awaitingClarification) return;
    sendMessage(inputValue);
    setInputValue('');
  };

  return (
      <div className="flex h-screen overflow-hidden bg-soft-bg text-soft-text">
        <Sidebar
            ref={sidebarRef}
            token={token}
            currentSessionId={currentSessionId}
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
              <Chat logs={logs} />
            </section>

            <section className="flex-1 overflow-y-auto p-8 bg-soft-bg">
              <ArtifactViewer
                  step={viewStep}
                  data={artifacts[viewStep]}
                  query={initialQuery}
                  awaitingClarification={awaitingClarification}
                  onClarify={sendClarification}
              />
            </section>
          </div>

          <footer className="p-6 border-t border-soft-border bg-white shrink-0">
            <form onSubmit={handleSubmit} className="max-w-4xl mx-auto">
                <div className="relative group">
                    <textarea
                        rows="2"
                        placeholder="Например: Собери динамику инфляции по странам ЕС за последние 5 лет..."
                        className="w-full bg-soft-bg border border-soft-border rounded-xl p-4 pr-32 text-sm focus:ring-2 focus:ring-soft-accent/20 focus:border-soft-accent outline-none transition-all resize-none shadow-sm"
                        value={inputValue}
                        onChange={(e) => setInputValue(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                handleSubmit(e);
                            }
                        }}
                        disabled={isProcessing || awaitingClarification}
                    />
                    <div className="absolute right-3 bottom-3">
                        <button
                            type="submit"
                            className="btn-primary flex items-center gap-2 text-sm font-semibold h-10 px-6"
                            disabled={isProcessing || awaitingClarification}
                        >
                            {isProcessing ? (
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
          </footer>
        </div>
      </div>
  );
}
