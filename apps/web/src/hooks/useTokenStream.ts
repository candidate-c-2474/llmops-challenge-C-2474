// useTokenStream.ts
import { useState, useRef } from "react";

export interface MetricStrip {
  ttft_ms: number;
  tokens_per_sec: number;
  cache_hit: boolean;
  backend: string;
}

export interface ChatEvent {
  type: "token" | "tool_call" | "tool_result" | "done" | "error";
  content?: string;
  name?: string;
  arguments?: Record<string, any>;
  metrics?: MetricStrip;
}

export function useTokenStream() {
  const [streamData, setStreamData] = useState<string>("");
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [metrics, setMetrics] = useState<MetricStrip | null>(None);
  const abortControllerRef = useRef<AbortController | null>(null);

  const startStream = async (message: string, history: any[] = []) => {
    setStreamData("");
    setIsStreaming(true);
    setMetrics(null);
    
    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history }),
        signal: abortController.signal
      });

      if (!response.body) throw new Error("ReadableStream not supported.");
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.trim() || !line.startsWith("data: ")) continue;
          const parsed: ChatEvent = JSON.parse(line.slice(6));
          
          if (parsed.type === "token" && parsed.content) {
            setStreamData((prev) => prev + parsed.content);
          } else if (parsed.type === "done" && parsed.metrics) {
            setMetrics(parsed.metrics);
          } else if (parsed.type === "error") {
            setStreamData((prev) => prev + `\nError: ${parsed.content}`);
          }
        }
      }
    } catch (err: any) {
      if (err.name === "AbortError") {
        setStreamData((prev) => prev + "\n[Generation Canceled by User]");
      } else {
        setStreamData((prev) => prev + `\n[Stream Error: ${err.message}]`);
      }
    } finally {
      setIsStreaming(false);
      abortControllerRef.current = null;
    }
  };

  const cancelStream = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  return { streamData, isStreaming, metrics, startStream, cancelStream };
}