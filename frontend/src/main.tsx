import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ApiProvider } from "./api/ApiContext";
import { SessionProvider } from "./session/SessionContext";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <ApiProvider>
          <App />
        </ApiProvider>
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
