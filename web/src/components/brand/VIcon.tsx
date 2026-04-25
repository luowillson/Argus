type IconName = "search" | "arrow" | "spark" | "bookmark" | "back";

type Props = {
  name: IconName;
  size?: number;
  className?: string;
};

export function VIcon({ name, size = 16, className }: Props) {
  const common = {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className,
    "aria-hidden": true,
  };
  switch (name) {
    case "search":
      return (
        <svg {...common}>
          <circle cx="11" cy="11" r="7" />
          <line x1="21" y1="21" x2="16.5" y2="16.5" />
        </svg>
      );
    case "arrow":
      return (
        <svg {...common}>
          <line x1="4" y1="12" x2="20" y2="12" />
          <polyline points="14 6 20 12 14 18" />
        </svg>
      );
    case "spark":
      return (
        <svg {...common}>
          <path d="M12 3 L13.6 10.4 L21 12 L13.6 13.6 L12 21 L10.4 13.6 L3 12 L10.4 10.4 Z" fill="currentColor" stroke="none" />
        </svg>
      );
    case "bookmark":
      return (
        <svg {...common}>
          <path d="M6 3 H18 V21 L12 17 L6 21 Z" />
        </svg>
      );
    case "back":
      return (
        <svg {...common}>
          <line x1="20" y1="12" x2="4" y2="12" />
          <polyline points="10 6 4 12 10 18" />
        </svg>
      );
  }
}
