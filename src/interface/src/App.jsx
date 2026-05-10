import React from 'react';
import './styles.css';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import ArtifactViewer from './components/ArtifactViewer';
import TraceLog from './components/TraceLog';
import Stepper from './components/Stepper';
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
  const {
    currentStep,
    setCurrentStep,
    logs,
    artifactData,
    isProcessing,
    sendMessage
  } = useAssistant();

  return (
      <div className="app-layout">
        <Sidebar />

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