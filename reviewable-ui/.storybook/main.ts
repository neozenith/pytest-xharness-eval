/**
 * Storybook 9/10, react-vite. The builder loads this project's own `vite.config.ts`
 * as its base config (aliases, the `@/*` path, the `process.env` defines tamagui's
 * web build needs), so nothing is re-declared here.
 */
import type { StorybookConfig } from "@storybook/react-vite";

const config: StorybookConfig = {
  stories: ["../src/**/*.stories.@(ts|tsx)"],
  addons: ["@storybook/addon-a11y", "@storybook/addon-docs", "@storybook/addon-vitest"],
  framework: {
    name: "@storybook/react-vite",
    options: {},
  },
  typescript: {
    reactDocgen: "react-docgen-typescript",
  },
};

export default config;
