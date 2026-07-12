"use client";

import { useState, useEffect } from "react";
import { fetchWithAuth } from "../api";
import { 
  Activity, FileText, MessageSquare, Database, Clock, 
  TrendingUp, AlertCircle, Loader2, Zap, BrainCircuit, ShieldCheck, CheckCircle2
} from "lucide-react";
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend
} from "recharts";

interface UserStatistics {
  total_documents: number;
  total_chunks: number;
  total_sessions: number;
  total_messages: number;
  documents_by_type: { document_type: string; count: number }[];
  last_activity: string | null;
  total_queries: number;
  queries_today: number;
  queries_this_week: number;
  tokens_prompt: number;
  tokens_completion: number;
  tokens_prompt_today: number;
  tokens_completion_today: number;
  avg_embedding_ms: number;
  avg_retrieval_ms: number;
  avg_llm_ms: number;
  avg_total_ms: number;
  avg_retrieval_score: number;
  avg_faithfulness: number;
  avg_context_length: number;
  avg_output_tokens: number;
  source_distribution: { retrieval_source: string; count: number }[];
  chunks_distribution: { num_retrieved_chunks: number; count: number }[];
  rewrite_stats: { rewritten: number; original: number };
  judge_distribution: { judge_decision: string; count: number }[];
  max_output_tokens: number;
  min_output_tokens: number;
  cache_hits: number;
  cache_misses: number;
  time_saved_ms: number;
}

const COLORS = ['#0ea5e9', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899', '#f43f5e'];

export default function DashboardView({ username }: { username: string }) {
  const [stats, setStats] = useState<UserStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetchWithAuth("/user/statistics");
        if (!res.ok) throw new Error("Failed to load statistics");
        const data = await res.json();
        setStats(data);
      } catch (err: any) {
        setError(err.message || "An error occurred");
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-zinc-50 dark:bg-zinc-950">
        <Loader2 size={32} className="animate-spin text-blue-500 mb-4" />
        <p className="text-zinc-500">Loading comprehensive analytics...</p>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-6">
        <div className="bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 p-4 rounded-xl flex items-center gap-3">
          <AlertCircle size={20} />
          <p className="font-medium">{error || "Failed to load data"}</p>
        </div>
      </div>
    );
  }

  if (!stats.rewrite_stats) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-6">
        <div className="bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400 p-4 rounded-xl flex flex-col items-center gap-3">
          <AlertCircle size={24} />
          <p className="font-medium">Backend is still updating...</p>
          <p className="text-sm">The new analytics metrics aren't available yet. If you just deployed the update, try refreshing the page or asking a new question first.</p>
        </div>
      </div>
    );
  }

  const latencyData = [
    { name: 'Embedding', time: stats.avg_embedding_ms },
    { name: 'Retrieval', time: stats.avg_retrieval_ms },
    { name: 'LLM Gen', time: stats.avg_llm_ms },
  ];

  const totalTokens = stats.tokens_prompt + stats.tokens_completion;
  const hitRate = stats.cache_hits + stats.cache_misses > 0 
    ? Math.round((stats.cache_hits / (stats.cache_hits + stats.cache_misses)) * 100) 
    : 0;

  const rewriteTotal = (stats.rewrite_stats?.rewritten || 0) + (stats.rewrite_stats?.original || 0);
  const rewriteSuccess = rewriteTotal > 0 ? Math.round(((stats.rewrite_stats?.original || 0) / rewriteTotal) * 100) : 100;

  return (
    <div className="flex flex-col h-full bg-zinc-50 dark:bg-zinc-950 p-6 md:p-12 overflow-y-auto">
      <div className="max-w-7xl w-full mx-auto animate-fade-in-up space-y-12 pb-12">
        
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-2xl bg-blue-600 text-white flex items-center justify-center font-bold text-2xl uppercase shadow-lg shadow-blue-600/20">
              {username ? username.charAt(0) : "U"}
            </div>
            <div>
              <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">AI Telemetry Analytics</h1>
              <p className="text-zinc-500 text-lg">System architecture, latency, and AI usage metrics.</p>
            </div>
          </div>
        </div>

        {/* 1. AI USAGE ANALYTICS */}
        <section>
          <h2 className="text-xl font-bold mb-6 text-zinc-900 dark:text-zinc-50 flex items-center gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-2">
            <Activity className="text-blue-500" /> AI Usage Analytics
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <MetricCard title="Total Queries" value={stats.total_queries} sub={`${stats.queries_today} today | ${stats.queries_this_week} this week`} />
            <MetricCard title="Avg Response Time" value={`${(stats.avg_total_ms / 1000).toFixed(2)}s`} sub="End-to-end latency" />
            <MetricCard title="Total Tokens Used" value={totalTokens.toLocaleString()} sub={`${stats.tokens_prompt.toLocaleString()} prompt | ${stats.tokens_completion.toLocaleString()} comp`} />
          </div>
          
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm">
              <h3 className="text-zinc-500 font-medium mb-4 text-sm uppercase tracking-wider">Average Latency Breakdown (ms)</h3>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={latencyData} layout="vertical" margin={{ top: 0, right: 30, left: 20, bottom: 0 }}>
                    <XAxis type="number" />
                    <YAxis dataKey="name" type="category" width={100} tick={{fill: '#888'}} />
                    <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                    <Bar dataKey="time" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm flex flex-col justify-center">
              <h3 className="text-zinc-500 font-medium mb-6 text-sm uppercase tracking-wider">Token Usage (Today)</h3>
              <div className="grid grid-cols-2 gap-8 text-center">
                <div>
                  <div className="text-4xl font-bold text-zinc-900 dark:text-zinc-50 mb-2">{stats.tokens_prompt_today.toLocaleString()}</div>
                  <div className="text-zinc-500 font-medium">Prompt Tokens</div>
                </div>
                <div>
                  <div className="text-4xl font-bold text-zinc-900 dark:text-zinc-50 mb-2">{stats.tokens_completion_today.toLocaleString()}</div>
                  <div className="text-zinc-500 font-medium">Completion Tokens</div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 2. RAG ANALYTICS */}
        <section>
          <h2 className="text-xl font-bold mb-6 text-zinc-900 dark:text-zinc-50 flex items-center gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-2">
            <BrainCircuit className="text-purple-500" /> RAG Analytics
          </h2>
          
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm col-span-1 lg:col-span-1">
              <h3 className="text-zinc-500 font-medium mb-4 text-sm uppercase tracking-wider">Retrieval Sources</h3>
              <div className="h-48">
                {stats.source_distribution.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={stats.source_distribution} dataKey="count" nameKey="retrieval_source" cx="50%" cy="50%" innerRadius={40} outerRadius={70}>
                        {stats.source_distribution.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-zinc-500">No data</div>
                )}
              </div>
            </div>
            
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm col-span-1 lg:col-span-2">
              <h3 className="text-zinc-500 font-medium mb-4 text-sm uppercase tracking-wider">Chunks Retrieved per Query</h3>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stats.chunks_distribution}>
                    <XAxis dataKey="num_retrieved_chunks" tick={{fill: '#888'}} />
                    <YAxis tick={{fill: '#888'}} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard title="Avg Retrieval Score" value={stats.avg_retrieval_score.toFixed(3)} sub="Cross-Encoder / BM25 Avg" />
            <MetricCard title="Original Query Acc." value={`${rewriteSuccess}%`} sub={`${stats.rewrite_stats.rewritten} rewritten automatically`} />
            <MetricCard title="Avg Context Length" value={Math.round(stats.avg_context_length).toLocaleString()} sub="Tokens injected into prompt" />
            <MetricCard title="Avg Faithfulness" value={`${(stats.avg_faithfulness * 100).toFixed(1)}%`} sub={`${(stats.avg_faithfulness).toFixed(2)} / 1.0 LLM Judge`} />
          </div>
        </section>

        {/* 3. SEMANTIC CACHE & 4. MEDICAL STATS */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-12">
          <section>
            <h2 className="text-xl font-bold mb-6 text-zinc-900 dark:text-zinc-50 flex items-center gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-2">
              <Zap className="text-amber-500" /> Semantic Cache Analytics
            </h2>
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm mb-6 flex justify-between items-center">
              <div>
                <p className="text-zinc-500 font-medium mb-1 uppercase tracking-wider text-sm">Hit Rate</p>
                <h3 className="text-4xl font-bold text-amber-500">{hitRate}%</h3>
              </div>
              <div className="text-right">
                <p className="text-zinc-900 dark:text-zinc-100 font-semibold mb-1">{stats.cache_hits} Hits</p>
                <p className="text-zinc-500">{stats.cache_misses} Misses</p>
              </div>
            </div>
            
            <div className="grid grid-cols-2 gap-6">
              <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm">
                <p className="text-zinc-500 font-medium mb-2 text-sm">Total Time Saved</p>
                <p className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">{(stats.time_saved_ms / 1000).toFixed(1)}s</p>
              </div>
              <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm">
                <p className="text-zinc-500 font-medium mb-2 text-sm">Estimated Money Saved</p>
                <p className="text-2xl font-bold text-emerald-500">${(stats.cache_hits * 0.002).toFixed(4)}</p>
                <p className="text-xs text-zinc-400 mt-1">Based on API limits</p>
              </div>
            </div>
          </section>

          <section>
            <h2 className="text-xl font-bold mb-6 text-zinc-900 dark:text-zinc-50 flex items-center gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-2">
              <FileText className="text-emerald-500" /> Medical Statistics
            </h2>
            <div className="bg-white dark:bg-zinc-900 rounded-2xl p-6 border border-zinc-200 dark:border-zinc-800 shadow-sm h-[264px] flex flex-col">
              <h3 className="text-zinc-500 font-medium mb-4 text-sm uppercase tracking-wider">Document Distribution</h3>
              <div className="flex-1">
                {stats.documents_by_type.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={stats.documents_by_type} dataKey="count" nameKey="document_type" cx="50%" cy="50%" innerRadius={50} outerRadius={80}>
                        {stats.documents_by_type.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend layout="vertical" verticalAlign="middle" align="right" />
                    </PieChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-zinc-500">No documents uploaded.</div>
                )}
              </div>
            </div>
          </section>
        </div>

        {/* 5. LLM PERFORMANCE */}
        <section>
          <h2 className="text-xl font-bold mb-6 text-zinc-900 dark:text-zinc-50 flex items-center gap-2 border-b border-zinc-200 dark:border-zinc-800 pb-2">
            <ShieldCheck className="text-rose-500" /> LLM Performance
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <MetricCard title="Avg Output Tokens" value={Math.round(stats.avg_output_tokens).toLocaleString()} sub="Per generation" />
            <MetricCard title="Avg Gen Time" value={`${(stats.avg_llm_ms / 1000).toFixed(2)}s`} sub="Model latency only" />
            <MetricCard title="Longest Response" value={stats.max_output_tokens.toLocaleString()} sub="Max output tokens" />
            <MetricCard title="Shortest Response" value={stats.min_output_tokens.toLocaleString()} sub="Min output tokens" />
          </div>
        </section>

      </div>
    </div>
  );
}

function MetricCard({ title, value, sub }: { title: string, value: string | number, sub: string }) {
  return (
    <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-200 dark:border-zinc-800 p-6 flex flex-col group hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors">
      <p className="text-zinc-500 font-medium mb-3 text-sm uppercase tracking-wider">{title}</p>
      <h3 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50 mb-2">{value}</h3>
      <p className="text-sm text-zinc-500 flex items-center gap-1"><CheckCircle2 size={14} className="text-emerald-500"/> {sub}</p>
    </div>
  );
}
