"use client";

import { useState, useEffect } from "react";
import { v4 as uuidv4 } from "uuid";
import Sidebar, { Session } from "./components/Sidebar";
import ChatArea, { Message } from "./components/ChatArea";
import ChatInput from "./components/ChatInput";
import ToolsView from "./components/ToolsView";
import DashboardView from "./components/DashboardView";
import AuthModal from "./components/AuthModal";
import { fetchWithAuth, fetchStreamWithAuth } from "./api";

export default function Home() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState("");
  const [username, setUsername] = useState("");
  const [isAboutOpen, setIsAboutOpen] = useState(false);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [theme, setTheme] = useState("system");
  const [currentView, setCurrentView] = useState<'chat' | 'tools' | 'dashboard'>('chat');

  // Check auth on load
  useEffect(() => {
    const savedTheme = localStorage.getItem("theme") || "system";
    setTheme(savedTheme);
    applyTheme(savedTheme);

    const token = localStorage.getItem("token");
    if (token) {
      setIsAuthenticated(true);
      fetchSessions();
      fetchMe();
    }
  }, []);

  const applyTheme = (t: string) => {
    const root = window.document.documentElement;
    root.classList.remove("dark");
    if (t === "dark" || (t === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
      root.classList.add("dark");
    }
  };

  const handleThemeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setTheme(val);
    localStorage.setItem("theme", val);
    applyTheme(val);
  };

  const fetchMe = async () => {
    try {
      const res = await fetchWithAuth("/me");
      const data = await res.json();
      setUsername(data.username);
    } catch (e) {
      console.error("Failed to fetch user", e);
    }
  };

  const fetchSessions = async () => {
    try {
      const res = await fetchWithAuth("/sessions");
      const data = await res.json();
      setSessions(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchChatHistory = async (sessionId: string) => {
    setMessages([]);
    try {
      const res = await fetchWithAuth(`/sessions/${sessionId}`);
      const history = await res.json();
      
      const formattedMessages: Message[] = history.map((msg: any) => ({
        id: uuidv4(),
        role: msg.role,
        content: msg.role === "assistant" && typeof msg.content === "string" && msg.content.startsWith("{")
          ? JSON.parse(msg.content)
          : msg.content
      }));
      setMessages(formattedMessages);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSelectSession = (id: string) => {
    setCurrentView('chat');
    setActiveSessionId(id);
    fetchChatHistory(id);
  };

  const handleNewChat = () => {
    setCurrentView('chat');
    setActiveSessionId(null);
    setMessages([]);
  };

  const handleOpenTools = () => {
    setCurrentView('tools');
    setActiveSessionId(null);
  };

  const handleOpenDashboard = () => {
    setCurrentView('dashboard');
    setActiveSessionId(null);
  };

  const handleRenameSession = async (id: string, newTitle: string) => {
    try {
      await fetchWithAuth(`/sessions/${id}/title`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: newTitle }),
      });
      // Optimistically update the title in the sidebar
      setSessions(prev => prev.map(s => s.session_id === id ? { ...s, title: newTitle } : s));
    } catch (e) {
      console.error("Failed to rename session", e);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem("token");
    setIsAuthenticated(false);
    setSessions([]);
    setMessages([]);
    setActiveSessionId(null);
    setUsername("");
  };

  const handleSendMessage = async (text: string, documentType?: string) => {
    let currentSessionId = activeSessionId;
    
    // Auto-generate session if we don't have one
    if (!currentSessionId) {
      currentSessionId = uuidv4();
      setActiveSessionId(currentSessionId);
    }

    // Add user message to UI immediately
    const userMsg: Message = { id: uuidv4(), role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);
    setIsTyping(true);

    try {
      const res = await fetchStreamWithAuth("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: text,
          session_id: currentSessionId,
          ...(documentType ? { document_type: documentType } : {})
        }),
      });

      if (!res.body) throw new Error("No readable stream");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.replace('data: ', '').trim();
            if (!dataStr) continue;
            
            try {
              const data = JSON.parse(dataStr);
              if (data.type === 'status') {
                setLoadingStatus(data.message);
              } else if (data.type === 'final') {
                const aiMsg: Message = { id: uuidv4(), role: "assistant", content: data.message };
                setMessages(prev => [...prev, aiMsg]);
                fetchSessions();
              }
            } catch(e) {}
          }
        }
      }
      
    } catch (e) {
      alert("Failed to send message.");
    } finally {
      setIsTyping(false);
      setLoadingStatus("");
    }
  };

  if (!isAuthenticated) {
    return (
      <AuthModal onLogin={() => {
        setIsAuthenticated(true);
        fetchSessions();
        fetchMe();
      }} />
    );
  }

  return (
    <div className="flex h-screen bg-zinc-50 dark:bg-black font-sans text-zinc-900 dark:text-zinc-50">
      
      {isAboutOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white dark:bg-zinc-950 rounded-2xl max-w-md w-full p-6 shadow-xl border border-zinc-200 dark:border-zinc-800">
            <h2 className="text-xl font-bold mb-4">About Medical AI</h2>
            <p className="text-zinc-600 dark:text-zinc-400 mb-6">
              This is a demonstration of an intelligent RAG Medical Assistant using LangGraph, Gemini, and FastAPI.
            </p>
            <button onClick={() => setIsAboutOpen(false)} className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 font-medium transition-colors">
              Close
            </button>
          </div>
        </div>
      )}

      {isSettingsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="bg-white dark:bg-zinc-950 rounded-2xl max-w-md w-full p-6 shadow-xl border border-zinc-200 dark:border-zinc-800">
            <h2 className="text-xl font-bold mb-4">Settings</h2>
            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium mb-1">Theme</label>
                <select 
                  value={theme}
                  onChange={handleThemeChange}
                  className="w-full border dark:border-zinc-700 rounded-lg p-2 bg-transparent text-zinc-900 dark:text-zinc-50"
                >
                  <option value="system">System Default</option>
                  <option value="light">Light</option>
                  <option value="dark">Dark</option>
                </select>
              </div>
            </div>
            <button onClick={() => setIsSettingsOpen(false)} className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2 font-medium transition-colors">
              Save Settings
            </button>
          </div>
        </div>
      )}

      <Sidebar 
        sessions={sessions}
        activeSessionId={activeSessionId}
        onSelectSession={handleSelectSession}
        onNewChat={handleNewChat}
        onOpenTools={handleOpenTools}
        onOpenDashboard={handleOpenDashboard}
        onLogout={handleLogout}
        onOpenSettings={() => setIsSettingsOpen(true)}
        onOpenAbout={() => setIsAboutOpen(true)}
        onRenameSession={handleRenameSession}
        username={username}
      />
      
      <main className="flex-1 flex flex-col relative h-full">
        {currentView === 'chat' ? (
          <>
            <div className="flex-1 overflow-hidden flex flex-col">
              <ChatArea messages={messages} loading={isTyping} loadingStatus={loadingStatus} />
            </div>
            
            <div className="shrink-0 pt-2 pb-4 px-4 bg-gradient-to-t from-zinc-50 via-zinc-50 dark:from-black dark:via-black">
              <ChatInput onSend={handleSendMessage} disabled={isTyping} />
            </div>
          </>
        ) : currentView === 'tools' ? (
          <div className="flex-1 overflow-hidden flex flex-col">
            <ToolsView />
          </div>
        ) : (
          <div className="flex-1 overflow-hidden flex flex-col">
            <DashboardView username={username} />
          </div>
        )}
      </main>
    </div>
  );
}
