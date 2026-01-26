import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

type NotificationType = 'success' | 'error' | 'info';

interface NotificationPayload {
  message: string;
  type?: NotificationType;
}

interface NotificationState extends NotificationPayload {
  open: boolean;
}

interface NotificationContextValue {
  showNotification: (payload: NotificationPayload) => void;
}

const NotificationContext = createContext<NotificationContextValue | undefined>(undefined);

const typeStyles: Record<NotificationType, string> = {
  success: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  error: 'border-red-200 bg-red-50 text-red-700',
  info: 'border-blue-200 bg-blue-50 text-blue-700',
};

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notification, setNotification] = useState<NotificationState>({
    message: '',
    type: 'info',
    open: false,
  });
  const timeoutRef = useRef<number | null>(null);

  const showNotification = useCallback((payload: NotificationPayload) => {
    setNotification({
      message: payload.message,
      type: payload.type ?? 'info',
      open: true,
    });
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = window.setTimeout(() => {
      setNotification((prev) => ({ ...prev, open: false }));
    }, 2000);
  }, []);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  const value = useMemo(() => ({ showNotification }), [showNotification]);

  return (
    <NotificationContext.Provider value={value}>
      {children}
      {notification.open && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/40 px-4">
          <div
            className={`w-full max-w-sm rounded-lg border px-4 py-3 text-sm font-semibold shadow-lg ${typeStyles[notification.type ?? 'info']}`}
          >
            {notification.message}
          </div>
        </div>
      )}
    </NotificationContext.Provider>
  );
}

export function useNotification() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotification must be used within a NotificationProvider');
  }
  return context;
}
