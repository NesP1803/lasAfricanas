type PaginationSize = 'sm' | 'md';

interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  size?: PaginationSize;
  className?: string;
}

const getPages = (page: number, totalPages: number) => {
  if (totalPages <= 1) return [1];
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages: Array<number | 'ellipsis'> = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);

  if (start > 2) {
    pages.push('ellipsis');
  }

  for (let current = start; current <= end; current += 1) {
    pages.push(current);
  }

  if (end < totalPages - 1) {
    pages.push('ellipsis');
  }

  pages.push(totalPages);
  return pages;
};

export default function Pagination({
  page,
  totalPages,
  onPageChange,
  size = 'md',
  className = '',
}: PaginationProps) {
  const pages = getPages(page, totalPages);
  const isSmall = size === 'sm';
  const buttonClasses = isSmall
    ? 'rounded-md border px-2 py-1 text-xs font-semibold transition'
    : 'rounded-md border px-3 py-1 text-sm font-semibold transition';

  return (
    <div className={`flex flex-wrap items-center justify-center gap-2 ${className}`}>
      <button
        type="button"
        disabled={page === 1}
        onClick={() => onPageChange(Math.max(1, page - 1))}
        className={`${buttonClasses} border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50`}
      >
        Anterior
      </button>
      <div className="flex flex-wrap items-center gap-1">
        {pages.map((item, index) => {
          if (item === 'ellipsis') {
            return (
              <span key={`ellipsis-${index}`} className="px-2 text-slate-400">
                ...
              </span>
            );
          }
          const isActive = item === page;
          return (
            <button
              key={item}
              type="button"
              onClick={() => onPageChange(item)}
              aria-current={isActive ? 'page' : undefined}
              className={`${buttonClasses} ${
                isActive
                  ? 'border-blue-600 bg-blue-600 text-white'
                  : 'border-slate-200 text-slate-600 hover:bg-slate-50'
              }`}
            >
              {item}
            </button>
          );
        })}
      </div>
      <button
        type="button"
        disabled={page >= totalPages}
        onClick={() => onPageChange(Math.min(totalPages, page + 1))}
        className={`${buttonClasses} border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50`}
      >
        Siguiente
      </button>
    </div>
  );
}
