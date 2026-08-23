/**
 * highlight.js, bundled (no CDN, ADR 0028): the core plus the languages the record
 * renderers name. Token colours are a small self-contained theme keyed to the page's
 * CSS variables, injected once, with a `.dark` variant; no stylesheet is fetched.
 */
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import css from "highlight.js/lib/languages/css";
import diff from "highlight.js/lib/languages/diff";
import ini from "highlight.js/lib/languages/ini";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import python from "highlight.js/lib/languages/python";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

const LANGUAGES: Record<string, unknown> = { bash, css, diff, ini, javascript, json, markdown, python, typescript, xml, yaml };
for (const [name, def] of Object.entries(LANGUAGES)) {
  if (!hljs.getLanguage(name)) hljs.registerLanguage(name, def as Parameters<typeof hljs.registerLanguage>[1]);
}

/** File extension -> highlight.js language, as the legacy `V.extLang` mapped them. */
export const extLang = (path: unknown): string =>
  (
    ({
      md: "markdown",
      py: "python",
      ts: "typescript",
      js: "javascript",
      json: "json",
      sh: "bash",
      bash: "bash",
      zsh: "bash",
      yml: "yaml",
      yaml: "yaml",
      toml: "ini",
      html: "xml",
      xml: "xml",
      css: "css",
      mmd: "",
    }) as Record<string, string>
  )[
    String(path ?? "")
      .split(".")
      .pop() ?? ""
  ] ?? "";

/** Highlighted HTML for `src`, or null when the language is unknown or highlighting fails. */
export function highlight(lang: string, src: string): string | null {
  if (!lang || !hljs.getLanguage(lang)) return null;
  try {
    return hljs.highlight(src, { language: lang, ignoreIllegals: true }).value;
  } catch {
    return null;
  }
}

const STYLE_ID = "xh-hljs-theme";
const THEME = `
.xh-code .hljs-comment, .xh-code .hljs-quote { color: #6a737d; font-style: italic; }
.xh-code .hljs-keyword, .xh-code .hljs-selector-tag, .xh-code .hljs-doctag, .xh-code .hljs-meta { color: #d73a49; }
.xh-code .hljs-string, .xh-code .hljs-regexp, .xh-code .hljs-addition { color: #22863a; }
.xh-code .hljs-number, .xh-code .hljs-literal, .xh-code .hljs-built_in, .xh-code .hljs-type, .xh-code .hljs-attr { color: #005cc5; }
.xh-code .hljs-title, .xh-code .hljs-section, .xh-code .hljs-name { color: #6f42c1; }
.xh-code .hljs-variable, .xh-code .hljs-template-variable, .xh-code .hljs-symbol, .xh-code .hljs-bullet { color: #e36209; }
.xh-code .hljs-deletion { color: #b31d28; background: rgba(255, 0, 0, .08); }
.xh-code .hljs-addition { background: rgba(0, 160, 0, .08); }
.xh-code .hljs-emphasis { font-style: italic; } .xh-code .hljs-strong { font-weight: 600; }
.dark .xh-code .hljs-comment, .dark .xh-code .hljs-quote { color: #8b949e; }
.dark .xh-code .hljs-keyword, .dark .xh-code .hljs-selector-tag, .dark .xh-code .hljs-doctag, .dark .xh-code .hljs-meta { color: #ff7b72; }
.dark .xh-code .hljs-string, .dark .xh-code .hljs-regexp, .dark .xh-code .hljs-addition { color: #7ee787; }
.dark .xh-code .hljs-number, .dark .xh-code .hljs-literal, .dark .xh-code .hljs-built_in, .dark .xh-code .hljs-type, .dark .xh-code .hljs-attr { color: #79c0ff; }
.dark .xh-code .hljs-title, .dark .xh-code .hljs-section, .dark .xh-code .hljs-name { color: #d2a8ff; }
.dark .xh-code .hljs-variable, .dark .xh-code .hljs-template-variable, .dark .xh-code .hljs-symbol, .dark .xh-code .hljs-bullet { color: #ffa657; }
.dark .xh-code .hljs-deletion { color: #ffa198; background: rgba(255, 0, 0, .15); }
.dark .xh-code .hljs-addition { background: rgba(0, 200, 0, .12); }
`;

/** Append the theme to <head> once; safe to call on every render. */
export function ensureTheme(): void {
  if (typeof document === "undefined" || document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = THEME;
  document.head.appendChild(style);
}
