"use client";

import { useState } from "react";
import { fetchWithAuth } from "../api";
import { Send, Activity, Loader2, AlertCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ToolExplanation {
  why_this_answer?: string;
  why_these_documents?: string;
  why_these_tools?: string;
  confidence?: string;
  evidence?: string;
}

interface ToolResponse {
  answer: string;
  explanation?: ToolExplanation | string;
}

export default function ToolsView() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ToolResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setResult(null);
    setError(null);

    try {
      const res = await fetchWithAuth("/tools", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: query }),
      });

      if (!res.ok) {
        throw new Error("Failed to run tool query");
      }

      const data = await res.json();
      setResult(data);
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  const renderExplanation = (exp: ToolExplanation | string | undefined) => {
    if (!exp) return null;
    
    // If it's a string, just render it as markdown
    if (typeof exp === 'string') {
      return <ReactMarkdown remarkPlugins={[remarkGfm]}>{exp}</ReactMarkdown>;
    }
    
    // If it's an object, render its keys beautifully
    return (
      <div className="space-y-4">
        {exp.why_this_answer && (
          <div>
            <h4 className="font-semibold text-emerald-700 dark:text-emerald-400 mb-1">Why this answer?</h4>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{exp.why_this_answer}</ReactMarkdown>
          </div>
        )}
        {exp.why_these_tools && (
          <div>
            <h4 className="font-semibold text-emerald-700 dark:text-emerald-400 mb-1">Tools Used</h4>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{exp.why_these_tools}</ReactMarkdown>
          </div>
        )}
        {exp.confidence && (
          <div>
            <h4 className="font-semibold text-emerald-700 dark:text-emerald-400 mb-1">Confidence</h4>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{exp.confidence}</ReactMarkdown>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-zinc-50 dark:bg-zinc-950 p-6 md:p-12 overflow-y-auto">
      <div className="max-w-4xl w-full mx-auto flex flex-col h-full">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-emerald-100 dark:bg-emerald-900/50 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <Activity size={24} />
            </div>
            <h1 className="text-3xl font-bold text-zinc-900 dark:text-zinc-50">Clinical Tools</h1>
          </div>
          <p className="text-zinc-600 dark:text-zinc-400 text-lg">
            Run deterministic medical calculators, risk scores, and check drug interactions safely outside of your main chat history.
          </p>
        </div>

        <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-200 dark:border-zinc-800 p-6 mb-8">
          <form onSubmit={handleSubmit} className="relative">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. Calculate the ASCVD risk for a 55-year-old male smoker with diabetes..."
              className="w-full min-h-[120px] p-4 pr-14 bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500/50 transition-all text-zinc-900 dark:text-zinc-50 placeholder-zinc-400"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSubmit(e);
                }
              }}
            />
            <button
              type="submit"
              disabled={!query.trim() || loading}
              className="absolute bottom-4 right-4 p-2 bg-emerald-600 text-white rounded-lg hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
            </button>
          </form>
        </div>

        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/50 text-red-600 dark:text-red-400 p-4 rounded-xl flex items-center gap-3 mb-8">
            <AlertCircle size={20} />
            <p className="font-medium">{error}</p>
          </div>
        )}

        {result && (
          <div className="flex-1 flex flex-col gap-6 pb-12 animate-fade-in-up">
            <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-200 dark:border-zinc-800 overflow-hidden">
              <div className="bg-emerald-50 dark:bg-emerald-900/20 px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
                <h3 className="font-semibold text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
                  <Activity size={18} />
                  Calculated Result
                </h3>
              </div>
              <div className="p-6 prose prose-zinc dark:prose-invert max-w-none prose-p:leading-relaxed prose-pre:bg-zinc-100 dark:prose-pre:bg-zinc-950">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {result.answer}
                </ReactMarkdown>
              </div>
            </div>

            {result.explanation && (
              <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm border border-zinc-200 dark:border-zinc-800 overflow-hidden opacity-90">
                <div className="bg-zinc-50 dark:bg-zinc-800/50 px-6 py-4 border-b border-zinc-200 dark:border-zinc-800">
                  <h3 className="font-medium text-zinc-700 dark:text-zinc-300">Explanation</h3>
                </div>
                <div className="p-6 prose prose-zinc dark:prose-invert max-w-none text-sm">
                  {renderExplanation(result.explanation)}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
