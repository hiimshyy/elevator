import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { LiveRegionProvider } from "./a11y/LiveRegionProvider";
import App from "./App";
import { ThemeProvider } from "./theme/ThemeProvider";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ThemeProvider>
      <LiveRegionProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </LiveRegionProvider>
    </ThemeProvider>
  </React.StrictMode>
);
