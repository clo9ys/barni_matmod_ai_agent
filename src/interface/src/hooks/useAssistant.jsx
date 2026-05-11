import { useState, useCallback } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';

export function useAssistant(token) {
    const [currentSessionId, setCurrentSessionId] = useState(null);
    const [currentStep, setCurrentStep] = useState(0);
    const [viewStep, setViewStep] = useState(0);
    const [logs, setLogs] = useState([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
    const [artifacts, setArtifacts] = useState({});
    const [isProcessing, setIsProcessing] = useState(false);
    const [initialQuery, setInitialQuery] = useState('');

    const resetAssistant = useCallback(() => {
        setCurrentSessionId(null);
        setCurrentStep(0);
        setViewStep(0);
        setLogs([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
        setArtifacts({});
        setInitialQuery('');
        setIsProcessing(false);
    }, []);

    const loadResearch = useCallback(async (sessionId) => {
        setIsProcessing(true);
        setCurrentSessionId(sessionId);
        try {
            const res = await fetch(`http://localhost:8000/api/v1/research/${sessionId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();

            setInitialQuery(data.query);
            setCurrentStep(data.current_step);
            setViewStep(1); // При загрузке показываем первый шаг

            // МАППИНГ: Превращаем сырые данные из БД в формат для карточек
            const mappedArtifacts = {};

            if (data.definition) {
                mappedArtifacts[1] = {
                    geography: data.definition.geography?.join(', ') || '',
                    timeframe: data.definition.time_period?.start || '...',
                    perspective: data.definition.subject_area || 'Экономика',
                    questions: data.definition.clarifying_questions || []
                };
            }

            // Шаг 2: Источники (вытаскиваем первый датасет из плана или используем данные о источниках)
            if (data.assembly_plan && data.assembly_plan.sources && data.assembly_plan.sources.length > 0) {
                const bestDs = data.assembly_plan.sources[0];
                mappedArtifacts[2] = {
                    title: bestDs.title,
                    tags: bestDs.tags || [],
                    description: bestDs.description,
                    url: bestDs.source_url || '#'
                };
            }

            if (data.design && data.design.hypotheses) {
                mappedArtifacts[3] = {
                    hypotheses: data.design.hypotheses.map((h, i) => ({
                        id: i,
                        title: h.hypothesis,
                        metrics: h.required_indicators || [],
                        selected: true
                    }))
                };
            }

            // Шаг 4: План (пока просто пометка о наличии)
            if (data.assembly_plan) {
                mappedArtifacts[4] = data.assembly_plan;
            }

            // Шаг 5: Сгенерированный код
            if (data.generated_script) {
                mappedArtifacts[5] = { code: data.generated_script };
            }

            // Шаг 6: Финальная сборка
            if (data.result_data) {
                mappedArtifacts[6] = { message: "Данные успешно собраны", details: data.result_data, file_url: data.result_file };
            }

            setArtifacts(mappedArtifacts);
            setLogs([{ text: 'История успешно загружена', type: 'dimmed' }]);
        } catch (e) {
            console.error("Ошибка загрузки истории", e);
            setLogs([{ text: 'Ошибка загрузки истории', type: 'error' }]);
        } finally {
            setIsProcessing(false);
        }
    }, [token]);

    const sendMessage = useCallback(async (message) => {
        if (!message.trim()) return;

        setIsProcessing(true);
        setInitialQuery(message);
        setLogs([{ text: 'Запуск задачи...', type: 'normal' }]);
        setArtifacts({});
        setCurrentStep(0);
        setViewStep(0);

        // Добавляем контроллер для жесткого прерывания реконнектов
        const ctrl = new AbortController();

        try {
            const response = await fetch('http://localhost:8000/api/v1/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ query: message })
            });

            if (!response.ok) throw new Error('Ошибка запуска');
            const { task_id } = await response.json();
            setCurrentSessionId(task_id);

            await fetchEventSource(`http://localhost:8000/api/v1/stream/${task_id}`, {
                headers: { 'Authorization': `Bearer ${token}` },
                signal: ctrl.signal, // Передаем сигнал отмены
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
                        } else if (data.type === 'done') {
                            setIsProcessing(false);
                            setLogs(prev => [...prev, { text: 'Анализ завершен', type: 'dimmed' }]);
                            ctrl.abort(); // Жестко прерываем реконнект
                        } else if (data.type === 'error') {
                            setIsProcessing(false);
                            setLogs(prev => [...prev, { text: `Ошибка: ${data.message}`, type: 'error' }]);
                            ctrl.abort(); // Жестко прерываем реконнект
                        }
                    } catch (parseError) {
                        console.warn("Ошибка парсинга JSON из потока:", msg.data);
                    }
                },
                onerror(err) {
                    // Игнорируем ошибку AbortError (мы сами ее вызвали)
                    if (err.name === 'AbortError') return;
                    setIsProcessing(false);
                    throw err; // Прокидываем ошибку дальше, чтобы остановить SSE
                }
            });
        } catch (error) {
            if (error.name !== 'AbortError') {
                setLogs(prev => [...prev, { text: `Ошибка: ${error.message}`, type: 'error' }]);
                setIsProcessing(false);
            }
        }
    }, [token]);

    return {
        currentSessionId,
        currentStep, viewStep, setViewStep,
        logs, artifacts, isProcessing,
        initialQuery, sendMessage, loadResearch, resetAssistant
    };
}