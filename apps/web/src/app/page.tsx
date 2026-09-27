'use client';

import React, { useState } from 'react';
import { useTokenStream } from '../hooks/useTokenStream';
import { MetricsStrip } from '../components/MetricsStrip';

export default function Home() {
  const [inputQuery, setInputQuery] = useState('');
  const { messages, sendMessage, isStreaming, stopStreaming, metrics } = useTokenStream();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputQuery.trim()) return;
    sendMessage(inputQuery);
    setInputQuery('');
  };

  return (
    <main className="flex flex-col h-screen bg-slate-950 text-slate-100">
      {/* Header */}
      <header className="bg-slate-900 border-b border-slate-800 px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
            RoomFit Copilot
          </h1>
          <p className="text-xs text-slate-400">
            AI Furniture Shopping Assistant with Hybrid RAG & Tool-Calling
          </p>
        </div>
        <span className="text-xs font-mono bg-slate-800 px-3 py-1.5 rounded-full border border-slate-700 text-slate-300">
          Candidate ID: C-XXXX
        </span>
      </header>

      {/* Metrics Strip */}
      <MetricsStrip metrics={metrics} isStreaming={isStreaming} />

      {/* Messages Window */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4 max-w-4xl mx-auto w-full">
        {messages.length === 0 ? (
          <div className="text-center py-20 text-slate-500">
            <p className="text-lg font-medium text-slate-400 mb-2">Welcome to RoomFit Copilot!</p>
            <p className="text-sm">Ask about furniture, check spatial fit, or compare catalog items.</p>
            <div className="flex justify-center gap-2 mt-6">
              <button
                onClick={() => sendMessage('I need a standing desk for a small home office')}
                className="text-xs bg-slate-900 border border-slate-800 hover:border-slate-700 px-3 py-2 rounded-lg text-slate-300"
              >
                "Standing desk for home office"
              </button>
              <button
                onClick={() => sendMessage('Check if desk DESK-001 fits in a space 150x100x80 cm')}
                className="text-xs bg-slate-900 border border-slate-800 hover:border-slate-700 px-3 py-2 rounded-lg text-slate-300"
              >
                "Check fit for DESK-001"
              </button>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div className={`max-w-2xl px-4 py-3 rounded-2xl text-sm ${
                msg.role === 'user'
                  ? 'bg-indigo-600 text-white rounded-br-none'
                  : 'bg-slate-900 border border-slate-800 text-slate-200 rounded-bl-none'
              }`}>
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content || (isStreaming && 'Thinking...')}</p>
              </div>
              <span className="text-[10px] text-slate-500 mt-1 px-1">
                {msg.role === 'user' ? 'You' : 'Copilot'}
              </span>
            </div>
          ))
        )}
      </div>

      {/* Input Bar & Controls */}
      <div className="border-t border-slate-800 p-4 bg-slate-900 max-w-4xl mx-auto w-full">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder="Type your message (e.g., Find me an ergonomic office chair)..."
            disabled={isStreaming}
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-indigo-500 text-slate-100 disabled:opacity-50"
          />

          {isStreaming ? (
            <button
              type="button"
              onClick={stopStreaming}
              className="bg-rose-600 hover:bg-rose-500 text-white px-5 py-3 rounded-xl text-sm font-medium transition-colors"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!inputQuery.trim()}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white px-6 py-3 rounded-xl text-sm font-medium transition-colors"
            >
              Send
            </button>
          )}
        </form>
      </div>
    </main>
  );
}
