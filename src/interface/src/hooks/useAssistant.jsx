import { useState, useCallback } from 'react';

export function useAssistant() {
    const [currentStep, setCurrentStep] = useState(0);
    const [logs, setLogs] = useState([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
    const [artifactData, setArtifactData] = useState(null);
    const [isProcessing, setIsProcessing] = useState(false);

    const sendMessage = useCallback(async (message) => {
        if (!message.trim()) return;

        setIsProcessing(true);
        setLogs([{ text: 'Отправка запроса на сервер...', type: 'normal' }]);
        setCurrentStep(0);
        setArtifactData(null); // Очищаем старые артефакты

        try {
            // 1. Инициируем задачу на бэкенде
            const response = await fetch('http://localhost:8000/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: message })
            });

            if (!response.ok) throw new Error('Ошибка сети');

            const { task_id } = await response.json();
            setLogs(prev => [...prev, { text: `Задача ${task_id} создана. Подключение к потоку...`, type: 'dimmed' }]);

            // 2. Слушаем SSE поток (Server-Sent Events)
            const eventSource = new EventSource(`http://localhost:8000/api/stream/${task_id}`);

            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case 'log':
                        setLogs(prev => [...prev, { text: data.message, type: 'normal' }]);
                        break;
                    case 'step_update':
                        setCurrentStep(data.step);
                        if (data.artifact) setArtifactData(data.artifact);
                        break;
                    case 'done':
                        setLogs(prev => [...prev, { text: 'Исследование завершено.', type: 'dimmed' }]);
                        setIsProcessing(false);
                        eventSource.close();
                        break;
                    case 'error':
                        setLogs(prev => [...prev, { text: `ОШИБКА: ${data.message}`, type: 'error' }]);
                        setIsProcessing(false);
                        eventSource.close();
                        break;
                    default:
                        console.warn('Неизвестный тип события:', data.type);
                }
            };

            eventSource.onerror = () => {
                setLogs(prev => [...prev, { text: 'Потеряно соединение с сервером.', type: 'error' }]);
                setIsProcessing(false);
                eventSource.close();
            };

        } catch (error) {
            console.error(error);
            setLogs(prev => [...prev, { text: 'Ошибка инициализации. Проверьте бэкенд.', type: 'error' }]);
            setIsProcessing(false);
        }
    }, []);

    return { currentStep, setCurrentStep, logs, artifactData, isProcessing, sendMessage };
}