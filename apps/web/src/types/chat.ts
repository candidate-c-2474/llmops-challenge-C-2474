export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  toolCalls?: Array<{
    name: string;
    arguments: Record<string, unknown>;
  }>;
  timestamp: Date;
}

export interface StreamMetrics {
  ttftMs: number | null;
  tokensPerSec: number | null;
  totalTokens: number;
  cacheHit: 'exact' | 'semantic' | 'miss' | null;
  activeBackend: 'vLLM (GPU)' | 'llama.cpp (CPU)' | 'FakeBackend';
  elapsedSec: number | null;
}

export interface Product {
  id: string;
  name: string;
  category: string;
  price: number;
  currency: string;
  stock: number;
  dimensions?: {
    width: number;
    height: number;
    depth: number;
    weight_kg?: number;
  };
  description?: string;
}
