import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { ApiProvider } from "./api/ApiContext";
import { AccountProvider } from "./session/AccountContext";
import { SessionProvider } from "./session/SessionContext";
import "./styles.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <SessionProvider>
        <AccountProvider>
          <ApiProvider>
            <App />
          </ApiProvider>
        </AccountProvider>
      </SessionProvider>
    </BrowserRouter>
  </StrictMode>,
);
