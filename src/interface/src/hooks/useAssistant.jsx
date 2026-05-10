import { useState, useCallback } from 'react';
import { fetchEventSource } from '@microsoft/fetch-event-source';

export function useAssistant(token) {
    const [currentStep, setCurrentStep] = useState(0); // Прогресс агента
    const [viewStep, setViewStep] = useState(0);       // Что видит пользователь
    const [logs, setLogs] = useState([{ text: 'Ожидание запроса...', type: 'dimmed' }]);
    const [artifacts, setArtifacts] = useState({});   // Объект: { шаг: данные }
    const [isProcessing, setIsProcessing] = useState(false);
    const [initialQuery, setInitialQuery] = useState('');

    // Функция для загрузки старого исследования из истории
    const loadResearch = useCallback(async (sessionId) => {
        setIsProcessing(true);
        try {
            const res = await fetch(`http://localhost:8000/api/v1/research/${sessionId}`, {
                headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await res.json();

            setInitialQuery(data.query);
            setCurrentStep(data.current_step);
            setViewStep(1); // Показываем первый результат

            // Мапим данные из БД в формат артефактов
            setArtifacts({
                1: data.definition,
                2: data.design,
                3: data.structure,
                4: data.assembly_plan
            });
            setLogs([{ text: 'История загружена', type: 'dimmed' }]);
        } catch (e) {
            console.error("Ошибка загрузки истории", e);
        } finally {
            setIsProcessing(false);
        }
    }, [token]);

    const sendMessage = useCallback(async (message) => {
        if (!message.trim()) return;
        setIsProcessing(true);
        setInitialQuery(message);
        setArtifacts({});
        setCurrentStep(0);
        setViewStep(0);
        setLogs([{ text: 'Запуск задачи...', type: 'normal' }]);

        try {
            const response = await fetch('http://localhost:8000/api/v1/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({ query: message })
            });
            const { task_id } = await response.json();

            await fetchEventSource(`http://localhost:8000/api/v1/stream/${task_id}`, {
                headers: { 'Authorization': `Bearer ${token}` },
                onmessage(msg) {
                    const data = JSON.parse(msg.data);
                    if (data.type === 'log') {
                        setLogs(prev => [...prev, { text: data.message, type: 'normal' }]);
                    } else if (data.type === 'step_update') {
                        setCurrentStep(data.step);
                        setViewStep(data.step); // Авто-переключение на новый шаг
                        if (data.artifact) {
                            setArtifacts(prev => ({ ...prev, [data.step]: data.artifact }));
                        }
                    } else if (data.type === 'done') {
                        setIsProcessing(false);
                    }
                }
            });
        } catch (error) {
            setIsProcessing(false);
        }
    }, [token]);

    return {
        currentStep, viewStep, setViewStep,
        logs, artifacts, isProcessing,
        initialQuery, sendMessage, loadResearch
    };
}