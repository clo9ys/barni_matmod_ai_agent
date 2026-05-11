import { useState, useCallback } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';

export function useAssistant(token) {
    const [currentStep, setCurrentStep] = useState(0);
    const [logs, setLogs] = useState([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
    const [artifactData, setArtifactData] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);

    const sendMessage = useCallback(async (message) => {
        if (!message.trim()) return;

        setIsProcessing(true);
        setLogs([{ text: 'Авторизация и запуск задачи...', type: 'normal' }]);
        setArtifactData(null);

        try {
            // Шаг 1: Запуск задачи (POST)
            const response = await fetch('http://localhost:8000/api/v1/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ query: message })
            });

            if (!response.ok) throw new Error('Ошибка авторизации или запуска');

            const { task_id } = await response.json();

            // Шаг 2: Подключение к стриму (SSE) через fetch-event-source
            await fetchEventSource(`http://localhost:8000/api/v1/stream/${task_id}`, {
                headers: { 'Authorization': `Bearer ${token}` },
                onmessage(msg) {
                    const data = JSON.parse(msg.data);

                    switch (data.type) {
                        case 'log':
                            setLogs(prev => [...prev, { text: data.message, type: 'normal' }]);
                            break;
                        case 'step_update':
                            setCurrentStep(data.step);
                            // Маппинг согласно гайду:
                            // Step 1: ResearchDefinitionCard (geography, timeframe...)
                            // Step 2: HypothesisCard (hypotheses[])
                            // Step 4: SourceCard (title, tags, url...)
                            if (data.artifact) {
                                setArtifactData(data.artifact);
                            }
                            break;
                        case 'done':
                            setLogs(prev => [...prev, { text: 'Исследование успешно завершено.', type: 'dimmed' }]);
                            setIsProcessing(false);
                            break;
                        case 'error':
                            setLogs(prev => [...prev, { text: `Ошибка: ${data.message}`, type: 'error' }]);
                            setIsProcessing(false);
                            break;
                    }
                },
                onerror(err) {
                    console.error('SSE Error:', err);
                    setIsProcessing(false);
                    throw err; // Позволяет библиотеке сделать реконнект или упасть
                }
            });

        } catch (error) {
            setLogs(prev => [...prev, { text: `Критическая ошибка: ${error.message}`, type: 'error' }]);
            setIsProcessing(false);
        }
    }, [token]);

    return { currentStep, setCurrentStep, logs, artifactData, isProcessing, sendMessage };
}