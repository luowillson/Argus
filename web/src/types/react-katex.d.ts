declare module "react-katex" {
  import type { ComponentType, ReactNode } from "react";

  type KatexProps = {
    children?: ReactNode;
    errorColor?: string;
    math?: string;
    renderError?: (error: Error) => ReactNode;
  };

  export const InlineMath: ComponentType<KatexProps>;
  export const BlockMath: ComponentType<KatexProps>;
}
