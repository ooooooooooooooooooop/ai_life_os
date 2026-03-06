const variants = {
  primary: 'bg-gradient-to-r from-blue-500 to-blue-600 text-white shadow-lg shadow-blue-500/50 hover:shadow-xl hover:shadow-blue-500/70 hover:-translate-y-0.5',
  secondary: 'bg-transparent border border-white/20 text-gray-300 hover:bg-white/5 hover:text-white',
  success: 'bg-gradient-to-r from-green-500 to-green-600 text-white shadow-lg shadow-green-500/50 hover:shadow-xl hover:shadow-green-500/70',
  danger: 'bg-gradient-to-r from-red-500 to-red-600 text-white shadow-lg shadow-red-500/50 hover:shadow-xl hover:shadow-red-500/70',
};

const sizes = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
};

export default function Button({
  children,
  variant = 'primary',
  size = 'md',
  className = '',
  disabled = false,
  loading = false,
  ...props
}) {
  return (
    <button
      className={`
        inline-flex items-center justify-center
        font-semibold rounded-full
        transition-all duration-200
        disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none
        ${variants[variant]}
        ${sizes[size]}
        ${className}
      `}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
      )}
      {children}
    </button>
  );
}
