import { useState, useRef, useCallback } from 'react';
import { Message, StreamMetrics } from '../types/chat';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function useTokenStream() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [metrics, setMetrics] = useState<StreamMetrics>({
    ttftMs: null,
    tokensPerSec: null,
    totalTokens: 0,
    cacheHit: null,
    activeBackend: 'vLLM (GPU)',
    elapsedSec: null,
  });

  const abortControllerRef = useRef<AbortController | null>(null);

  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
    }
  }, []);

  const sendMessage = useCallback(async (userQuery: string) => {
    if (!userQuery.trim() || isStreaming) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: userQuery,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setIsStreaming(true);

    const assistantMsgId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, assistantMessage]);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    const startTime = performance.now();
    let firstTokenTime: number | null = null;
    let tokenCount = 0;

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userQuery }),
        signal: controller.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const rawData = line.replace('data: ', '').trim();
            if (!rawData) continue;

            try {
              const event = JSON.parse(rawData);

              if (event.type === 'token') {
                if (!firstTokenTime) {
                  firstTokenTime = performance.now();
                  const ttft = Math.round(firstTokenTime - startTime);
                  setMetrics((m) => ({ ...m, ttftMs: ttft }));
                }

                tokenCount += 1;
                const elapsed = (performance.now() - startTime) / 1000;
                const tps = tokenCount / Math.max(elapsed, 0.001);

                setMetrics((m) => ({
                  ...m,
                  totalTokens: tokenCount,
                  tokensPerSec: Math.round(tps * 10) / 10,
                  elapsedSec: Math.round(elapsed * 10) / 10,
                }));

                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMsgId
                      ? { ...msg, content: msg.content + event.content }
                      : msg
                  )
                );
              }
            } catch (err) {
              // Non-JSON or SSE event line
            }
          }
        }
      }
    } catch (error: unknown) {
      if ((error as Error).name !== 'AbortError') {
        console.error('Stream error:', error);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  }, [isStreaming]);

  return {
    messages,
    sendMessage,
    isStreaming,
    stopStreaming,
    metrics,
  };
}
