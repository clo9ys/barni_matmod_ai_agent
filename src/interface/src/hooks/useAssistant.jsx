import { useState, useCallback, useRef } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';

export function useAssistant(token, onNewTask) {
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [currentStep, setCurrentStep] = useState(0);
    const [viewStep, setViewStep] = useState(0);
    const [logs, setLogs] = useState([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
    const [artifacts, setArtifacts] = useState({});
    const [isProcessing, setIsProcessing] = useState(false);
    const [awaitingClarification, setAwaitingClarification] = useState(false);
    const [initialQuery, setInitialQuery] = useState('');
    const [sessionId, setSessionId] = useState(null);

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
        setCurrentSessionId(null);
        setCurrentStep(0);
        setViewStep(0);
        setLogs([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
        setArtifacts({});
        setInitialQuery('');
        setIsProcessing(false);
        setAwaitingClarification(false);
        setSessionId(null);
    }, [_abortActive, _cancelActiveWorker]);

    const loadResearch = useCallback(async (sid) => {
        _abortActive();
        _cancelActiveWorker();
        setIsProcessing(true);
        try {
            const res = await fetch(`http://localhost:8000/api/v1/research/${sid}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();

            setSessionId(sid);
            setCurrentSessionId(sid);
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
                    title: bestDs.title,
                    tags: bestDs.tags || [],
                    description: bestDs.description,
                    url: bestDs.source_url || '#'
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
                mappedArtifacts[4] = {
                    combination_strategy: plan.combination_strategy,
                    join_key: plan.join_key,
                    output_columns: plan.output_schema?.columns || plan.output_columns,
                    sources: (plan.primary_sources || []).map(src => ({
                        dataset_id: src.dataset_id,
                        indicator: src.indicator_name || src.indicator,
                        years: src.years_used || src.years,
                        role: src.role || 'primary',
                    })),
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
                        if (data.type === 'awaiting_clarification') {
                            setIsProcessing(false);
                            setAwaitingClarification(true);
                            setLogs(prev => [...prev, { text: '❓ Ответьте на уточняющие вопросы чтобы продолжить', type: 'normal' }]);
                        } else if (data.type === 'log') {
                            setLogs(prev => [...prev, { text: data.message, type: 'normal' }]);
                        } else if (data.type === 'step_update') {
                            setCurrentStep(data.step);
                            setViewStep(data.step);
                            if (data.artifact) {
                                setArtifacts(prev => ({ ...prev, [data.step]: data.artifact }));
                            }
                        } else if (data.type === 'done') {
                            setIsProcessing(false);
                            setAwaitingClarification(false);
                            setLogs(prev => [...prev, { text: 'Анализ завершен', type: 'dimmed' }]);
                            activeTaskIdRef.current = null;
                            ctrl.abort();
                        } else if (data.type === 'error') {
                            setIsProcessing(false);
                            setAwaitingClarification(false);
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
                    throw err;
                }
            });
        } catch (error) {
            if (error.name !== 'AbortError') {
                setLogs(prev => [...prev, { text: `Ошибка потока: ${error.message}`, type: 'error' }]);
                setIsProcessing(false);
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
        setAwaitingClarification(false);
        setInitialQuery(message);
        setLogs([{ text: 'Запуск задачи...', type: 'normal' }]);
        setArtifacts({});
        setCurrentStep(0);
        setViewStep(0);
        setSessionId(null);
        setCurrentSessionId(null);

        try {
            const response = await fetch('http://localhost:8000/api/v1/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ query: message })
            });
            if (!response.ok) throw new Error('Ошибка запуска');
            const { task_id, session_id } = await response.json();
            setSessionId(session_id || task_id);
            setCurrentSessionId(task_id);
            if (onNewTask) onNewTask();
            await _subscribeToStream(task_id);
        } catch (error) {
            if (error.name !== 'AbortError') {
                setLogs(prev => [...prev, { text: `Ошибка: ${error.message}`, type: 'error' }]);
                setIsProcessing(false);
            }
        }
    }, [token, _subscribeToStream, _abortActive, _cancelActiveWorker, onNewTask]);

    const sendClarification = useCallback(async (answer) => {
        if (!answer.trim()) return;
        const combinedQuery = `${initialQuery}\n\nОтветы на уточняющие вопросы: ${answer}`;

        _abortActive();
        _cancelActiveWorker();

        setAwaitingClarification(false);
        setIsProcessing(true);
        setLogs(prev => [...prev, { text: `📝 Уточнение отправлено`, type: 'normal' }]);
        setArtifacts(prev => {
            const next = { ...prev };
            for (let s = 2; s <= 6; s++) delete next[s];
            return next;
        });
        setCurrentStep(1);
        setViewStep(1);

        try {
            const response = await fetch('http://localhost:8000/api/v1/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
                body: JSON.stringify({ query: combinedQuery, skip_clarification: true })
            });
            if (!response.ok) throw new Error('Ошибка запуска');
            const { task_id, session_id } = await response.json();
            setSessionId(session_id || task_id);
            setCurrentSessionId(task_id);
            if (onNewTask) onNewTask();
            await _subscribeToStream(task_id);
        } catch (error) {
            if (error.name !== 'AbortError') {
                setLogs(prev => [...prev, { text: `Ошибка: ${error.message}`, type: 'error' }]);
                setIsProcessing(false);
            }
        }
    }, [initialQuery, token, _subscribeToStream, _abortActive, _cancelActiveWorker, onNewTask]);

    return {
        currentSessionId,
        currentStep, viewStep, setViewStep,
        logs, artifacts, isProcessing, awaitingClarification,
        initialQuery, sessionId,
        sendMessage, sendClarification, loadResearch, resetAssistant
    };
}
