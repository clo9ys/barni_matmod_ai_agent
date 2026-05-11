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
            setViewStep(data.current_step || 1);

            // МАППИНГ: Превращаем сырые данные из БД в формат для карточек
            // Порядок шагов совпадает с тем, что отправляет research.py:
            // 1 - параметры запроса, 2 - источник, 3 - гипотезы, 4 - валидация плана, 5 - код, 6 - результат
            const mappedArtifacts = {};

            // Шаг 1: параметры запроса
            if (data.definition) {
                mappedArtifacts[1] = {
                    geography: data.definition.geography?.join(', ') || '',
                    timeframe: data.definition.time_period?.start || '...',
                    perspective: data.definition.subject_area || 'Экономика',
                    questions: data.definition.clarifying_questions || []
                };
            }

            // Шаг 2: лучший найденный источник
            if (data.assembly_plan?.sources?.length > 0) {
                const bestDs = data.assembly_plan.sources[0];
                mappedArtifacts[2] = {
                    title: bestDs.title,
                    tags: bestDs.tags || [],
                    description: bestDs.description,
                    url: bestDs.source_url || '#'
                };
            }

            // Шаг 3: гипотезы
            if (data.design?.hypotheses) {
                mappedArtifacts[3] = {
                    hypotheses: data.design.hypotheses.map((h, i) => ({
                        id: i,
                        title: h.hypothesis,
                        metrics: h.required_indicators || [],
                        selected: true
                    }))
                };
            }

            // Шаг 4: план сборки прошёл валидацию (карточка не требует данных)
            if (data.assembly_plan) {
                mappedArtifacts[4] = { plan: 'Валидация пройдена' };
            }

            // Шаг 5: сгенерированный скрипт
            if (data.generated_script) {
                mappedArtifacts[5] = { code: data.generated_script };
            }

            // Шаг 6: результат выполнения
            if (data.result_data) {
                mappedArtifacts[6] = data.result_data;
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