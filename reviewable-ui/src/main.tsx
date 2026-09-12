import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/App";
import "./styles.css";

const host = document.getElementById("Reviewable");
if (!host) throw new Error("#Reviewable is missing from index.html");
createRoot(host).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
