export default function App() {
  const [token, setToken] = useState(localStorage.getItem('access_token'));

  const {
    currentStep, viewStep, setViewStep,
    logs, artifacts, isProcessing,
    initialQuery, sendMessage, loadResearch
  } = useAssistant(token);

  return (
      <div className="app-layout">
        {/* Теперь Sidebar умеет вызывать загрузку */}
        <Sidebar token={token} onHistoryClick={loadResearch} />

        <div className="main-area">
          <header className="top-bar">
            {/* Степпер управляет viewStep, а не currentStep */}
            <Stepper
                steps={STEPS}
                current={currentStep}
                selected={viewStep}
                onSelect={setViewStep}
            />
          </header>

          <div className="workspace">
            <section className="chat-panel">
              <Chat onSend={sendMessage} disabled={isProcessing} query={initialQuery} />
            </section>

            <section className="artifact-panel">
              {/* Показываем артефакт именно для того шага, который выбран */}
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