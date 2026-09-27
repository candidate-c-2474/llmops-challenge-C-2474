import React from 'react';
import { StreamMetrics } from '../types/chat';

interface Props {
  metrics: StreamMetrics;
  isStreaming: boolean;
}

export const MetricsStrip: React.FC<Props> = ({ metrics, isStreaming }) => {
  return (
    <div className="bg-slate-900 text-slate-200 border-b border-slate-800 px-4 py-2 text-xs flex flex-wrap items-center justify-between gap-4 font-mono">
      <div className="flex items-center space-[#8px] gap-4">
        <span className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-full ${isStreaming ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
          Status: <strong className="text-white">{isStreaming ? 'Streaming' : 'Idle'}</strong>
        </span>

        <span>
          Backend: <strong className="text-indigo-400">{metrics.activeBackend}</strong>
        </span>
      </div>

      <div className="flex items-center gap-6">
        <span>
          TTFT: <strong className="text-amber-300">{metrics.ttftMs ? `${metrics.ttftMs} ms` : '—'}</strong>
        </span>

        <span>
          Speed: <strong className="text-emerald-300">{metrics.tokensPerSec ? `${metrics.tokensPerSec} tok/s` : '—'}</strong>
        </span>

        <span>
          Tokens: <strong className="text-cyan-300">{metrics.totalTokens}</strong>
        </span>

        <span>
          Cache: <strong className="text-purple-300">{metrics.cacheHit || 'Miss'}</strong>
        </span>
      </div>
    </div>
  );
};
