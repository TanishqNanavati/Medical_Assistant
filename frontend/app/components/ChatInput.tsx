"use client";

import { useState, useRef } from "react";
import { Send, Paperclip, Loader2 } from "lucide-react";
import { fetchWithAuth } from "../api";

interface ChatInputProps {
  onSend: (message: string, documentType?: string) => void;
  disabled: boolean;
}

export default function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [message, setMessage] = useState("");
  const [docType, setDocType] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string>("Uploading...");
  const [toastMessage, setToastMessage] = useState<{ text: string, type: 'success' | 'error' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const showToast = (text: string, type: 'success' | 'error') => {
    setToastMessage({ text, type });
    setTimeout(() => setToastMessage(null), 3000);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !disabled) {
      onSend(message, docType || undefined);
      setMessage("");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!docType) {
      showToast("Please select a Document Type before uploading.", "error");
      e.target.value = "";
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("document_type", docType);

    try {
      const res = await fetchWithAuth("/upload", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      
      let taskId = data.task_id;
      while (true) {
        const statusRes = await fetchWithAuth(`/upload/status/${taskId}`);
        const statusData = await statusRes.json();
        
        if (statusData.task_status === "SUCCESS") {
          setIsUploading(false);
          setUploadProgress("Uploading...");
          showToast("File processed successfully!", "success");
          break;
        } else if (statusData.task_status === "FAILURE") {
          throw new Error("Upload failed");
        } else if (statusData.task_status === "PROGRESS" && statusData.task_info?.status) {
          setUploadProgress(statusData.task_info.status);
        }
        
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    } catch (err) {
      setIsUploading(false);
      setUploadProgress("Uploading...");
      showToast("Upload failed. Make sure you are logged in.", "error");
    } finally {
      e.target.value = "";
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto p-4 relative mt-2">
      {/* Toast Notification */}
      {toastMessage && (
        <div className={`absolute -top-12 left-1/2 -translate-x-1/2 px-4 py-2 rounded-full shadow-lg text-sm font-medium transition-all duration-300 ${
          toastMessage.type === 'success' 
            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/80 dark:text-emerald-100 border border-emerald-200 dark:border-emerald-800' 
            : 'bg-red-100 text-red-800 dark:bg-red-900/80 dark:text-red-100 border border-red-200 dark:border-red-800'
        }`}>
          {toastMessage.text}
        </div>
      )}

      <form 
        onSubmit={handleSubmit} className="relative flex flex-col bg-white dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 rounded-2xl shadow-sm focus-within:ring-2 focus-within:ring-blue-500 overflow-hidden">
        
        {/* Top toolbar */}
        <div className="flex items-center px-4 py-2 border-b border-zinc-100 dark:border-zinc-700/50 bg-zinc-50 dark:bg-zinc-800/80">
          <select
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            className="text-sm bg-transparent border-none text-zinc-600 dark:text-zinc-300 focus:outline-none cursor-pointer"
          >
            <option value="">All Documents (General)</option>
            <option value="patient_history">Patient History</option>
            <option value="lab_report">Lab Report</option>
            <option value="medical_guideline">Medical Guideline</option>
          </select>
        </div>

        {/* Text Area */}
        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          placeholder="Message Medical Assistant..."
          className="w-full max-h-48 min-h-[60px] resize-none px-4 py-3 bg-transparent border-none focus:outline-none text-zinc-900 dark:text-zinc-50 placeholder-zinc-400"
          rows={1}
        />

        {/* Bottom Toolbar */}
        <div className="flex items-center justify-between px-3 py-2">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="p-2 text-zinc-500 hover:text-zinc-700 dark:text-zinc-400 dark:hover:text-zinc-200 hover:bg-zinc-100 dark:hover:bg-zinc-700 rounded-lg transition-colors"
            title="Upload Document"
          >
            {isUploading ? <Loader2 size={20} className="animate-spin" /> : <Paperclip size={20} />}
          </button>
          <input
            type="file"
            ref={fileInputRef}
            className="hidden"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={handleFileUpload}
          />

          <button
            type="submit"
            disabled={!message.trim() || disabled || isUploading}
            className={`p-2 rounded-xl transition-colors ${
              (message.trim() || isUploading) && !disabled
                ? "bg-blue-600 text-white hover:bg-blue-700 shadow-sm"
                : "bg-zinc-100 dark:bg-zinc-700 text-zinc-400"
            }`}
          >
            {isUploading ? (
              <div className="flex items-center gap-2 px-1">
                <span className="text-sm font-medium">{uploadProgress}</span>
              </div>
            ) : (
              <Send size={18} className={message.trim() && !disabled ? "translate-x-0.5 -translate-y-0.5" : ""} />
            )}
          </button>
        </div>
      </form>
      <div className="text-center mt-2 text-xs text-zinc-500">
        Medical AI Assistant can make mistakes. Always verify clinical information.
      </div>
    </div>
  );
}
