"use client";

import { Bot, User, Copy, Check } from "lucide-react";
import { useState, useRef, useEffect } from "react";

export type Message = {
  id: string;
  role: "user" | "assistant";
  content: any; // Can be string for user, or complex JSON object for assistant
};

const CopyButton = ({ text }: { text: any }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    let textToCopy = typeof text === "string" ? text : text.answer || JSON.stringify(text);

    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200">
      <button 
        onClick={handleCopy}
        className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors p-1 rounded-md"
        title="Copy message"
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
      </button>
    </div>
  );
};

interface ChatAreaProps {
  messages: Message[];
  loading: boolean;
  loadingStatus?: string;
}

export default function ChatArea({ messages, loading, loadingStatus }: ChatAreaProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);
  
  const renderAssistantContent = (content: any) => {
    if (typeof content === "string") {
      return <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed">{content}</p>;
    }

    return (
      <div className="space-y-6 text-zinc-800 dark:text-zinc-200 leading-relaxed">
        {/* Answer block */}
        {content.answer && (
          <div>
            <div 
              className="prose dark:prose-invert max-w-none"
              dangerouslySetInnerHTML={{ __html: content.answer.replace(/\n/g, '<br/>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') }}
            />
          </div>
        )}

        {/* Explainability Block */}
        {content.explanation && (
          <div className="bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700/50 rounded-xl p-5 space-y-4">
            <h3 className="font-semibold text-lg flex items-center gap-2 text-zinc-900 dark:text-zinc-50 border-b border-zinc-200 dark:border-zinc-700 pb-2">
              <Bot size={18} className="text-blue-500" />
              Behind the Scenes
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <strong className="text-zinc-900 dark:text-zinc-300 block mb-1">Why this answer?</strong>
                <p className="text-zinc-600 dark:text-zinc-400">{content.explanation.why_this_answer}</p>
              </div>
              
              <div>
                <strong className="text-zinc-900 dark:text-zinc-300 block mb-1">Why these documents?</strong>
                <p className="text-zinc-600 dark:text-zinc-400">{content.explanation.why_these_documents}</p>
              </div>
              
              <div>
                <strong className="text-zinc-900 dark:text-zinc-300 block mb-1">Method Used</strong>
                <p className="text-zinc-600 dark:text-zinc-400">{content.explanation.why_these_tools}</p>
              </div>

              <div>
                <strong className="text-zinc-900 dark:text-zinc-300 block mb-1">Confidence</strong>
                <p className="text-zinc-600 dark:text-zinc-400">{content.explanation.confidence}</p>
              </div>
            </div>

            <div className="text-sm border-t border-zinc-200 dark:border-zinc-700 pt-3 mt-3">
              <strong className="text-zinc-900 dark:text-zinc-300 block mb-1">Evidence</strong>
              <p className="text-zinc-600 dark:text-zinc-400 italic">"{content.explanation.evidence}"</p>
            </div>
          </div>
        )}

        {/* Citations Block */}
        {content.citations && content.citations.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-300 mb-2">Sources Referenced:</h4>
            <div className="flex flex-wrap gap-2">
              {content.citations.map((cit: any, idx: number) => (
                <span key={idx} className="inline-flex items-center gap-1 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 px-2 py-1 rounded text-xs font-medium border border-blue-200 dark:border-blue-800">
                  {cit.id} {cit.source.split('/').pop()} (Page {cit.page})
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 py-8 custom-scrollbar">
      <div className="max-w-3xl mx-auto space-y-8 pb-10">
        {messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center mt-32 space-y-4">
            <div className="w-16 h-16 bg-blue-100 dark:bg-blue-900/30 rounded-2xl flex items-center justify-center mb-2">
              <Bot size={32} className="text-blue-600 dark:text-blue-400" />
            </div>
            <h2 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">How can I help you today?</h2>
            <p className="text-zinc-500 max-w-md">Upload medical reports, clinical guidelines, or patient history to begin an intelligent RAG session.</p>
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`flex gap-4 group ${msg.role === "assistant" ? "" : "justify-end"}`}>
              {msg.role === "assistant" && (
                <div className="w-8 h-8 shrink-0 bg-blue-100 dark:bg-blue-900/50 rounded-full flex items-center justify-center border border-blue-200 dark:border-blue-800">
                  <Bot size={18} className="text-blue-600 dark:text-blue-400" />
                </div>
              )}
              
              <div className={`flex flex-col gap-1 max-w-[85%] ${msg.role === "user" ? "items-end" : "items-start pt-1"}`}>
                <div className={`${
                  msg.role === "user" 
                    ? "bg-blue-600 text-white px-5 py-3 rounded-2xl rounded-tr-sm shadow-sm"
                    : ""
                }`}>
                  {msg.role === "user" ? (
                    <p className="leading-relaxed">{msg.content}</p>
                  ) : (
                    renderAssistantContent(msg.content)
                  )}
                </div>
                <div className="px-2 mt-1">
                  <CopyButton text={msg.content} />
                </div>
              </div>
            </div>
          ))
        )}

        {loading && (
          <div className="flex gap-4">
            <div className="w-8 h-8 shrink-0 bg-blue-100 dark:bg-blue-900/50 rounded-full flex items-center justify-center border border-blue-200 dark:border-blue-800">
              <Bot size={18} className="text-blue-600 dark:text-blue-400" />
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1 bg-zinc-100 dark:bg-zinc-800 px-4 py-3 rounded-2xl rounded-tl-sm h-[40px]">
                <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
                <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
                <div className="w-2 h-2 bg-zinc-400 rounded-full animate-bounce"></div>
              </div>
              {loadingStatus && (
                <span className="text-sm text-zinc-500 font-medium animate-pulse">{loadingStatus}</span>
              )}
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
