import { useState, useCallback } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';

export function useAssistant(token) {
    const [currentStep, setCurrentStep] = useState(0);
    const [viewStep, setViewStep] = useState(0);
    const [logs, setLogs] = useState([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
    const [artifacts, setArtifacts] = useState({});
    const [isProcessing, setIsProcessing] = useState(false);
    const [initialQuery, setInitialQuery] = useState('');

    const resetAssistant = useCallback(() => {
        setCurrentStep(0);
        setViewStep(0);
        setLogs([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
        setArtifacts({});
        setInitialQuery('');
        setIsProcessing(false);
    }, []);

    const loadResearch = useCallback(async (sessionId) => {
        setIsProcessing(true);
        try {
            const res = await fetch(`http://localhost:8000/api/v1/research/${sessionId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();

            setInitialQuery(data.query);
            setCurrentStep(data.current_step);
            setViewStep(1);

            setArtifacts({
                1: data.definition,
                2: data.design,
                3: data.structure,
                4: data.assembly_plan
            });
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
        currentStep, viewStep, setViewStep,
        logs, artifacts, isProcessing,
        initialQuery, sendMessage, loadResearch, resetAssistant
    };
}