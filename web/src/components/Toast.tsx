import React, { createContext, useContext, useState, ReactNode } from 'react';
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react';

type ToastType = 'success' | 'error' | 'info' | 'warning';

interface Toast {
  id: number;
  type: ToastType;
  title: string;
  message?: string;
  duration?: number;
}

interface ToastContextType {
  toasts: Toast[];
  showToast: (type: ToastType, title: string, message?: string, duration?: number) => void;
  removeToast: (id: number) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
};

interface ToastProviderProps {
  children: ReactNode;
}

export const ToastProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [nextId, setNextId] = useState(1);

  const showToast = (type: ToastType, title: string, message?: string, duration: number = 5000) => {
    const id = nextId;
    setNextId(nextId + 1);

    const newToast: Toast = { id, type, title, message, duration };
    setToasts((prev) => [...prev, newToast]);

    // Auto-remove after duration
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  };

  const removeToast = (id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  };

  return (
    <ToastContext.Provider value={{ toasts, showToast, removeToast }}>
      {children}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  );
};

interface ToastContainerProps {
  toasts: Toast[];
  removeToast: (id: number) => void;
}

const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, removeToast }) => {
  return (
    <div className="fixed top-4 right-4 z-50 space-y-2 max-w-sm">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onRemove={() => removeToast(toast.id)} />
      ))}
    </div>
  );
};

interface ToastItemProps {
  toast: Toast;
  onRemove: () => void;
}

const ToastItem: React.FC<ToastItemProps> = ({ toast, onRemove }) => {
  const typeConfig = {
    success: {
      icon: CheckCircle,
      bgColor: 'bg-green-900/90',
      borderColor: 'border-green-700',
      iconColor: 'text-green-400',
      titleColor: 'text-green-100',
    },
    error: {
      icon: AlertCircle,
      bgColor: 'bg-red-900/90',
      borderColor: 'border-red-700',
      iconColor: 'text-red-400',
      titleColor: 'text-red-100',
    },
    warning: {
      icon: AlertTriangle,
      bgColor: 'bg-yellow-900/90',
      borderColor: 'border-yellow-700',
      iconColor: 'text-yellow-400',
      titleColor: 'text-yellow-100',
    },
    info: {
      icon: Info,
      bgColor: 'bg-blue-900/90',
      borderColor: 'border-blue-700',
      iconColor: 'text-blue-400',
      titleColor: 'text-blue-100',
    },
  };

  const config = typeConfig[toast.type];
  const Icon = config.icon;

  return (
    <div
      className={`${config.bgColor} ${config.borderColor} border rounded-lg shadow-lg p-4 min-w-[300px] backdrop-blur-sm animate-slide-in-right`}
    >
      <div className="flex items-start gap-3">
        <Icon className={`w-5 h-5 ${config.iconColor} flex-shrink-0 mt-0.5`} />
        <div className="flex-1">
          <p className={`font-semibold ${config.titleColor}`}>{toast.title}</p>
          {toast.message && (
            <p className="text-gray-300 text-sm mt-1">{toast.message}</p>
          )}
        </div>
        <button
          onClick={onRemove}
          className="text-gray-400 hover:text-white transition-colors flex-shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
