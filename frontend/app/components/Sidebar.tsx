"use client";

import { Plus, MessageSquare, LogOut, Info, Settings, User } from "lucide-react";
import { useState, useRef, useEffect } from "react";

export type Session = {
  session_id: string;
  title: string;
  updated_at: string;
};

interface SidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onOpenTools: () => void;
  onOpenDashboard: () => void;
  onLogout: () => void;
  onOpenSettings: () => void;
  onOpenAbout: () => void;
  onRenameSession: (id: string, newTitle: string) => void;
  username: string;
}

export default function Sidebar({ sessions, activeSessionId, onSelectSession, onNewChat, onOpenTools, onOpenDashboard, onLogout, onOpenSettings, onOpenAbout, onRenameSession, username }: SidebarProps) {
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingSessionId && inputRef.current) {
      inputRef.current.focus();
    }
  }, [editingSessionId]);

  const handleDoubleClick = (id: string, currentTitle: string) => {
    setEditingSessionId(id);
    setEditTitle(currentTitle);
  };

  const handleSaveRename = (id: string) => {
    if (editTitle.trim()) {
      onRenameSession(id, editTitle.trim());
    }
    setEditingSessionId(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent, id: string) => {
    if (e.key === "Enter") {
      handleSaveRename(id);
    } else if (e.key === "Escape") {
      setEditingSessionId(null);
    }
  };

  return (
    <div className="w-64 bg-zinc-50 dark:bg-zinc-950 border-r border-zinc-200 dark:border-zinc-800 flex flex-col h-screen transition-all">
      
      {/* User Info Header */}
      <button 
        onClick={onOpenDashboard}
        className="p-4 border-b border-zinc-200 dark:border-zinc-800 flex items-center gap-3 mb-2 text-left hover:bg-zinc-100 dark:hover:bg-zinc-900 transition-colors w-full group"
        title="View Evaluation Dashboard"
      >
        <div className="w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-blue-600 dark:text-blue-400 font-bold uppercase shrink-0 group-hover:scale-105 transition-transform">
          {username ? username.charAt(0) : "U"}
        </div>
        <div className="truncate flex-1">
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50 truncate group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">{username || "User"}</p>
          <p className="text-xs text-zinc-500">View Statistics & Evaluation</p>
        </div>
      </button>

      <div className="px-4 pb-2 space-y-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-3 rounded-xl transition-colors font-medium shadow-sm"
        >
          <Plus size={20} />
          New Chat
        </button>
        <button
          onClick={onOpenTools}
          className="w-full flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-3 rounded-xl transition-colors font-medium shadow-sm"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
          Clinical Tools
        </button>
      </div>
      
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1 custom-scrollbar">
        {sessions.length === 0 ? (
          <p className="text-zinc-500 text-sm text-center mt-4">No recent chats</p>
        ) : (
          sessions.map((s) => (
            <button
              key={s.session_id}
              onClick={() => onSelectSession(s.session_id)}
              onDoubleClick={() => handleDoubleClick(s.session_id, s.title)}
              className={`w-full flex items-center gap-3 px-3 py-3 rounded-lg text-left transition-colors group ${
                activeSessionId === s.session_id
                  ? "bg-zinc-200 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-50"
                  : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-800/50"
              }`}
            >
              <MessageSquare size={18} className="shrink-0" />
              {editingSessionId === s.session_id ? (
                <input
                  ref={inputRef}
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onBlur={() => handleSaveRename(s.session_id)}
                  onKeyDown={(e) => handleKeyDown(e, s.session_id)}
                  className="bg-transparent border-none outline-none flex-1 truncate text-sm font-medium"
                  onClick={(e) => e.stopPropagation()}
                />
              ) : (
                <span className="truncate text-sm font-medium select-none">{s.title}</span>
              )}
            </button>
          ))
        )}
      </div>

      <div className="p-4 border-t border-zinc-200 dark:border-zinc-800 space-y-1">
        <button onClick={onOpenAbout} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors">
          <Info size={18} />
          <span className="text-sm font-medium">About</span>
        </button>
        <button onClick={onOpenSettings} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-800 transition-colors">
          <Settings size={18} />
          <span className="text-sm font-medium">Settings</span>
        </button>
        <button 
          onClick={onLogout}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
        >
          <LogOut size={18} />
          <span className="text-sm font-medium">Log out</span>
        </button>
      </div>
    </div>
  );
}
