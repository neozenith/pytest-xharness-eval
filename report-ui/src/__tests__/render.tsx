/** Test render with the Tamagui provider every component now expects above it. */
import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import { TamaguiProvider } from "tamagui";
import { config } from "@/tamagui.config";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <TamaguiProvider config={config} defaultTheme="light">
      {children}
    </TamaguiProvider>
  );
}

export const renderT = (ui: ReactElement, options?: RenderOptions): RenderResult => render(ui, { wrapper: Providers, ...options });
