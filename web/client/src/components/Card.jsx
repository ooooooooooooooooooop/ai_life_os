export default function Card({ children, className = '', hover = true }) {
  return (
    <div
      className={`
        bg-slate-800/70 backdrop-blur-md
        border border-white/10 rounded-2xl
        shadow-lg
        ${hover ? 'transition-all duration-200 hover:shadow-xl hover:-translate-y-1 hover:shadow-blue-500/20' : ''}
        ${className}
      `}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className = '' }) {
  return (
    <div className={`px-6 py-4 border-b border-white/10 ${className}`}>
      {children}
    </div>
  );
}

export function CardBody({ children, className = '' }) {
  return (
    <div className={`px-6 py-4 ${className}`}>
      {children}
    </div>
  );
}

export function CardFooter({ children, className = '' }) {
  return (
    <div className={`px-6 py-4 border-t border-white/10 ${className}`}>
      {children}
    </div>
  );
}
