import { clsx, type ClassValue } from "clsx";

/** Conditional class names for the semantic-CSS side of the page (index.css). */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}
