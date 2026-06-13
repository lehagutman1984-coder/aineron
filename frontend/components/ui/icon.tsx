import type { LucideIcon, LucideProps } from "lucide-react";

export type IconSize = "sm" | "md" | "lg";

const SIZE_MAP: Record<IconSize, number> = {
  sm: 16,
  md: 20,
  lg: 24,
};

interface IconProps extends Omit<LucideProps, "size"> {
  icon: LucideIcon;
  size?: IconSize | number;
}

export function Icon({ icon: LucideComponent, size = "md", ...props }: IconProps) {
  const px = typeof size === "number" ? size : SIZE_MAP[size];
  return <LucideComponent size={px} {...props} />;
}
