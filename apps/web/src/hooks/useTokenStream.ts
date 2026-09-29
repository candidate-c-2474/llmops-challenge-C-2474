'use client';

import { useState, useRef, useCallback } from "react";

export interface MetricStrip {
  ttft_ms: number;
  tokens_per_sec: number;
  cache_hit: boolean;
  backend: string;
}

export interface ProductCard {
  id: string;
  name: string;
  price: number;
  stock: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export interface ChatEvent {
  type: "token" | "tool_call" | "tool_result" | "done" | "error";
  content?: string;
  name?: string;
  arguments?: Record<string, unknown>;
  usage?: Record<string, unknown>;
}

interface UseTokenStreamResult {
  messages: ChatMessage[];
  isStreaming: boolean;
  metrics: MetricStrip | null;
  productCards: ProductCard[];
  sendMessage: (message: string, history?: ChatMessage[]) => Promise<void>;
  stopStreaming: () => void;
}

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function useTokenStream(): UseTokenStreamResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [metrics, setMetrics] = useState<MetricStrip | null>(null);
  const [productCards, setProductCards] = useState<ProductCard[]>([]);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(async (message: string, history: ChatMessage[] = []) => {
    // Append user message
    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      content: message,
    };
    const assistantId = `a-${Date.now()}`;
    const assistantMsg: ChatMessage = { id: assistantId, role: "assistant", content: "" };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);
    setMetrics(null);
    setProductCards([]);

    const abort = new AbortController();
    abortRef.current = abort;
    const t0 = performance.now();
    let firstTokenAt: number | null = null;
    let tokenCount = 0;

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          history: history.map((m) => ({ role: m.role, content: m.content })),
        }),
        signal: abort.signal,
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.trim() || !line.startsWith("data: ")) continue;
          let parsed: ChatEvent;
          try {
            parsed = JSON.parse(line.slice(6));
          } catch {
            continue;
          }

          if (parsed.type === "token" && parsed.content) {
            if (firstTokenAt === null) firstTokenAt = performance.now();
            tokenCount += 1;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: m.content + parsed.content } : m,
              ),
            );
          } else if (parsed.type === "tool_result" && parsed.content) {
            // Try to extract product cards from the tool result payload
            try {
              const payload = JSON.parse(parsed.content);
              if (Array.isArray(payload?.results)) {
                setProductCards(
                  payload.results.map((r: Record<string, unknown>) => ({
                    id: String(r.product_id ?? ""),
                    name: String(r.product_id ?? ""),
                    price: 0,
                    stock: 0,
                  })),
                );
              }
            } catch {
              // tool result is not JSON; ignore
            }
          } else if (parsed.type === "done") {
            const elapsed = (performance.now() - t0) / 1000;
            const ttft = firstTokenAt !== null ? firstTokenAt - t0 : 0;
            const tps = elapsed > 0 ? tokenCount / elapsed : 0;
            setMetrics({
              ttft_ms: Math.round(ttft),
              tokens_per_sec: Math.round(tps * 10) / 10,
              cache_hit: false,
              backend: "vllm",
            });
          } else if (parsed.type === "error") {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: m.content + `\n[Error: ${parsed.content ?? parsed}` }
                  : m,
              ),
            );
          }
        }
      }
    } catch (err) {
      const e = err as Error;
      if (e.name === "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + "\n[Canceled by user]" } : m,
          ),
        );
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + `\n[Stream error: ${e.message}]` } : m,
          ),
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, []);

  const stopStreaming = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
    }
  }, []);

  return { messages, isStreaming, metrics, productCards, sendMessage, stopStreaming };
}
