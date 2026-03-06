export default function Loading({ text = 'Loading...', size = 'md' }) {
  const sizes = {
    sm: 'h-8 w-8',
    md: 'h-12 w-12',
    lg: 'h-16 w-16',
  };

  return (
    <div className="flex flex-col items-center justify-center gap-4">
      <div
        className={`
          ${sizes[size]}
          border-4 border-slate-700 border-t-blue-500
          rounded-full animate-spin
        `}
      />
      {text && <p className="text-gray-400 text-sm">{text}</p>}
    </div>
  );
}

export function LoadingOverlay({ text = 'Loading...' }) {
  return (
    <div className="fixed inset-0 bg-slate-900/80 backdrop-blur-sm flex items-center justify-center z-50">
      <Loading text={text} size="lg" />
    </div>
  );
}

export function LoadingButton({ loading, children, ...props }) {
  return (
    <button {...props} disabled={loading || props.disabled}>
      {loading ? (
        <span className="flex items-center gap-2">
          <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
          </svg>
          Processing...
        </span>
      ) : (
        children
      )}
    </button>
  );
}

export function SkeletonCard() {
  return (
    <div className="bg-slate-800/70 backdrop-blur-md border border-white/10 rounded-2xl p-6 animate-pulse">
      <div className="h-4 bg-slate-700 rounded w-3/4 mb-4"></div>
      <div className="h-3 bg-slate-700 rounded w-1/2 mb-2"></div>
      <div className="h-3 bg-slate-700 rounded w-5/6 mb-4"></div>
      <div className="flex gap-2">
        <div className="h-8 bg-slate-700 rounded-full w-20"></div>
        <div className="h-8 bg-slate-700 rounded-full w-24"></div>
      </div>
    </div>
  );
}

export function SkeletonList({ count = 3 }) {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
