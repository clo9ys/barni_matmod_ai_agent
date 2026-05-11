import { useState, useCallback, useRef } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';

export function useAssistant(token) {
    const [currentStep, setCurrentStep] = useState(0);
    const [viewStep, setViewStep] = useState(0);
    const [logs, setLogs] = useState([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
    const [artifacts, setArtifacts] = useState({});
    const [isProcessing, setIsProcessing] = useState(false);
    const [isRefining, setIsRefining] = useState(false);
    const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);
    const [initialQuery, setInitialQuery] = useState('');
    const [sessionId, setSessionId] = useState(null);

    // Refs to cancel the active SSE stream and to know the active task id
    const activeCtrlRef = useRef(null);
    const activeTaskIdRef = useRef(null);

    const _abortActive = useCallback(() => {
        if (activeCtrlRef.current) {
            activeCtrlRef.current.abort();
            activeCtrlRef.current = null;
        }
    }, []);

    const _cancelActiveWorker = useCallback(() => {
        const tid = activeTaskIdRef.current;
        if (tid) {
            fetch(`http://localhost:8000/api/v1/stream/${tid}/cancel`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` },
            }).catch(() => {});
            activeTaskIdRef.current = null;
        }
    }, [token]);

    const resetAssistant = useCallback(() => {
        _abortActive();
        _cancelActiveWorker();
        setCurrentStep(0);
        setViewStep(0);
        setLogs([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
        setArtifacts({});
        setInitialQuery('');
        setIsProcessing(false);
        setIsRefining(false);
        setAwaitingConfirmation(false);
        setSessionId(null);
    }, [_abortActive, _cancelActiveWorker]);

    const loadResearch = useCallback(async (sid) => {
        _abortActive();
        _cancelActiveWorker();
        setIsProcessing(true);
        setAwaitingConfirmation(false);
        try {
            const res = await fetch(`http://localhost:8000/api/v1/research/${sid}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();

            setSessionId(sid);
            setInitialQuery(data.query);
            setCurrentStep(data.current_step);
            setViewStep(data.current_step || 1);

            const mappedArtifacts = {};

            if (data.definition) {
                const tp = data.definition.time_period || {};
                const start = tp.start, end = tp.end;
                let timeframe = 'Не задано';
                if (start && end) timeframe = start !== end ? `${start}-${end}` : String(start);
                else if (start || end) timeframe = String(start || end);
                mappedArtifacts[1] = {
                    geography: data.definition.geography?.join(', ') || '',
                    timeframe,
                    perspective: data.definition.subject_area || 'Экономика',
                    questions: data.definition.clarifying_questions || []
                };
            }
            if (data.assembly_plan?.sources?.length > 0) {
                const bestDs = data.assembly_plan.sources[0];
                mappedArtifacts[2] = {
                    title: bestDs.title, tags: bestDs.tags || [],
                    description: bestDs.description, url: bestDs.source_url || '#'
                };
            }
            if (data.design?.hypotheses) {
                mappedArtifacts[3] = {
                    hypotheses: data.design.hypotheses.map((h, i) => ({
                        id: i, title: h.hypothesis,
                        metrics: h.required_indicators || [], selected: true
                    }))
                };
            }
            if (data.assembly_plan?.plan) {
                const plan = data.assembly_plan.plan;
                const sources = (plan.primary_sources || []).map(src => ({
                    dataset_id: src.dataset_id,
                    indicator: src.indicator_name || src.indicator,
                    years: src.years_used || src.years,
                    role: src.role || 'primary',
                }));
                mappedArtifacts[4] = {
                    combination_strategy: plan.combination_strategy,
                    join_key: plan.join_key,
                    output_columns: plan.output_schema?.columns || plan.output_columns,
                    sources,
                };
            }
            if (data.generated_script) mappedArtifacts[5] = { code: data.generated_script };
            if (data.result_data) mappedArtifacts[6] = data.result_data;

            setArtifacts(mappedArtifacts);
            setLogs([{ text: 'История успешно загружена', type: 'dimmed' }]);
        } catch (e) {
            console.error('Ошибка загрузки истории', e);
            setLogs([{ text: 'Ошибка загрузки истории', type: 'error' }]);
        } finally {
            setIsProcessing(false);
        }
    }, [token, _abortActive, _cancelActiveWorker]);

    const _subscribeToStream = useCallback(async (taskId) => {
        // Abort any previous stream
        _abortActive();

        const ctrl = new AbortController();
        activeCtrlRef.current = ctrl;
        activeTaskIdRef.current = taskId;

        try {
            await fetchEventSource(`http://localhost:8000/api/v1/stream/${taskId}`, {
                headers: { 'Authorization': `Bearer ${token}` },
                signal: ctrl.signal,
                onmessage(msg) {
                    if (!msg.data) return;
                    try {
                        const data = JSON.parse(msg.data);
                        if (data.type === 'log') {
                            setLogs(prev => [...prev, { text: data.message, type: 'normal' }]);
                        } else if (data.type === 'step_update') {
                            setCurrentStep(data.step);
                            setViewStep(data.step);
                            if (data.artifact) {
                                setArtifacts(prev => ({ ...prev, [data.step]: data.artifact }));
                            }
                        } else if (data.type === 'awaiting_confirmation') {
                            setIsProcessing(false);
                            setIsRefining(false);
                            setAwaitingConfirmation(true);
                        } else if (data.type === 'done') {
                            setIsProcessing(false);
                            setIsRefining(false);
                            setAwaitingConfirmation(false);
                            setLogs(prev => [...prev, { text: 'Анализ завершен', type: 'dimmed' }]);
                            activeTaskIdRef.current = null;
                            ctrl.abort();
                        } else if (data.type === 'error') {
                            setIsProcessing(false);
                            setIsRefining(false);
                            setAwaitingConfirmation(false);
                            setLogs(prev => [...prev, { text: `Ошибка: ${data.message}`, type: 'error' }]);
                            activeTaskIdRef.current = null;
                            ctrl.abort();
                        }
                    } catch {
                        console.warn('Ошибка парсинга SSE:', msg.data);
                    }
                },
                onerror(err) {
                    if (err.name === 'AbortError') return;
                    setIsProcessing(false);
                    setIsRefining(false);
                    setAwaitingConfirmation(false);
                    throw err;
                }
            });
        } catch (error) {
            if (error.name !== 'AbortError') {
                setLogs(prev => [...prev, { text: `Ошибка потока: ${error.message}`, type: 'error' }]);
                setIsProcessing(false);
                setIsRefining(false);
                setAwaitingConfirmation(false);
            }
        } finally {
            if (activeCtrlRef.current === ctrl) {
                activeCtrlRef.current = null;
            }
        }
    }, [token, _abortActive]);

    const sendMessage = useCallback(async (message) => {
        if (!message.trim()) return;

        _abortActive();
        _cancelActiveWorker();

        setIsProcessing(true);
        setIsRefining(false);
        setAwaitingConfirmation(false);
        setInitialQuery(message);
        setLogs([{ text: 'Запуск задачи...', type: 'normal' }]);
        setArtifacts({});
        setCurrentStep(0);
        setViewStep(0);
        setSessionId(null);

        try {
            const response = await fetch('http://localhost:8000/api/v1/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ query: message })
            });
            if (!response.ok) throw new Error('Ошибка запуска');
            const { task_id, session_id } = await response.json();
            setSessionId(session_id || task_id);
            await _subscribeToStream(task_id);
        } catch (error) {
            if (error.name !== 'AbortError') {
                setLogs(prev => [...prev, { text: `Ошибка: ${error.message}`, type: 'error' }]);
                setIsProcessing(false);
            }
        }
    }, [token, _subscribeToStream, _abortActive, _cancelActiveWorker]);

    const confirmStep = useCallback(async () => {
        const taskId = activeTaskIdRef.current;
        if (!taskId) return;
        setAwaitingConfirmation(false);
        setIsProcessing(true);
        try {
            await fetch(`http://localhost:8000/api/v1/stream/${taskId}/continue`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${token}` }
            });
        } catch (e) {
            console.error('Ошибка подтверждения шага', e);
        }
    }, [token]);

    const refineFromStep = useCallback(async (fromStep, correction) => {
        if (!sessionId) return;

        // Cancel paused worker and abort SSE
        _cancelActiveWorker();
        _abortActive();

        setAwaitingConfirmation(false);
        setIsRefining(true);
        setIsProcessing(true);
        setArtifacts(prev => {
            const next = { ...prev };
            for (let s = fromStep; s <= 6; s++) delete next[s];
            return next;
        });
        setCurrentStep(fromStep - 1);
        setViewStep(fromStep);
        setLogs(prev => [...prev, { text: `🔄 Уточнение с шага ${fromStep}...`, type: 'normal' }]);

        try {
            const response = await fetch(`http://localhost:8000/api/v1/research/${sessionId}/refine`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ from_step: fromStep, correction })
            });
            if (!response.ok) throw new Error('Ошибка запуска уточнения');
            const { task_id } = await response.json();
            await _subscribeToStream(task_id);
        } catch (error) {
            if (error.name !== 'AbortError') {
                setLogs(prev => [...prev, { text: `Ошибка: ${error.message}`, type: 'error' }]);
                setIsRefining(false);
                setIsProcessing(false);
            }
        }
    }, [sessionId, token, _subscribeToStream, _abortActive, _cancelActiveWorker]);

    return {
        currentStep, viewStep, setViewStep,
        logs, artifacts, isProcessing, isRefining, awaitingConfirmation,
        initialQuery, sessionId,
        sendMessage, loadResearch, resetAssistant, confirmStep, refineFromStep
    };
}
