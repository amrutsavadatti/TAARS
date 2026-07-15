import React from "react";
import { createRoot } from "react-dom/client";
import { Dashboard } from "./Dashboard";
import "./styles/dashboard.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Root element #root not found.");
}

createRoot(root).render(
  <React.StrictMode>
    <Dashboard
      config={{
        apiKey: import.meta.env.VITE_TAARS_API_KEY || "dev-key",
        baseUrl: import.meta.env.VITE_TAARS_API_BASE_URL || "",
      }}
    />
  </React.StrictMode>
);
