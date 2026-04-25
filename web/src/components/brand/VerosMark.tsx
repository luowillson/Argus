type Props = {
  size?: number;
  className?: string;
};

export function VerosMark({ size = 18, className }: Props) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Veros mark"
      className={className}
    >
      <path
        d="M3 4 L12 21 L21 4"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
      <circle cx="12" cy="11.5" r="1.6" fill="currentColor" />
    </svg>
  );
}
