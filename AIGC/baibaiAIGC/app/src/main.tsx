import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import { desktopService } from "./lib/desktopService";
import { webService } from "./lib/webService";
import "./styles/global.css";

const runtimeMode = (import.meta.env.VITE_APP_RUNTIME ?? "desktop").toLowerCase();
const service = runtimeMode === "web" ? webService : desktopService;
const pickerLabel = runtimeMode === "web" ? "上传文档" : "选择文档";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App service={service} pickerLabel={pickerLabel} />
  </React.StrictMode>,
);
