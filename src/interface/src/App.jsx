import React, { useState } from 'react';
import './styles.css';
import Sidebar from './components/Sidebar';
import Chat from './components/Chat';
import ArtifactViewer from './components/ArtifactViewer';
import TraceLog from './components/TraceLog';
import Stepper from './components/Stepper';

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
  const [currentStep, setCurrentStep] = useState(0);

  return (
      <div className="app-layout">
        <Sidebar />

        <div className="main-area">
          <header className="top-bar">
            <Stepper steps={STEPS} current={currentStep} onSelect={setCurrentStep} />
          </header>

          <div className="workspace">
            <section className="chat-panel">
              <Chat />
            </section>

            <section className="artifact-panel">
              <ArtifactViewer currentStep={currentStep} />
            </section>
          </div>

          <footer className="trace-log">
            <TraceLog />
          </footer>
        </div>
      </div>
  );
}