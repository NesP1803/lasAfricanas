interface ConfirmModalProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: 'danger' | 'primary';
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

const confirmButtonStyles = {
  danger: 'bg-red-600 text-white hover:bg-red-700',
  primary: 'bg-blue-600 text-white hover:bg-blue-700',
};

export default function ConfirmModal({
  open,
  title,
  description,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  confirmVariant = 'primary',
  onConfirm,
  onCancel,
  loading = false,
}: ConfirmModalProps) {
  if (!open) return null;

  return (
    <div className="app-modal-backdrop z-[60] bg-black/40">
      <div className="app-modal-panel-md border border-slate-200">
        <div className="app-modal-body">
        <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
        {description && <p className="mt-2 text-sm text-slate-600">{description}</p>}
        <div className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end sm:gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="w-full rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-slate-50 sm:w-auto"
            disabled={loading}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`w-full rounded-md px-4 py-2 text-sm font-semibold transition sm:w-auto ${confirmButtonStyles[confirmVariant]}`}
            disabled={loading}
          >
            {loading ? 'Procesando...' : confirmLabel}
          </button>
        </div>
        </div>
      </div>
    </div>
  );
}
