"use client";

import { HubPage } from "../../components/hub/HubKit";
import { CycleProvider } from "../../components/cycle/CycleContext";
import { CycleTabs } from "../../components/cycle/CycleTabs";

export function CycleClient() {
  return (
    <HubPage title="Cycle">
      <CycleProvider>
        <header className="mb-5 print:hidden">
          <h1 className="m-0 text-h1 text-ink">Your cycle</h1>
          <p className="m-0 mt-1 text-body font-semibold text-muted">Estimates from your own logs. They can be wrong and they are not birth control.</p>
        </header>
        <CycleTabs />
      </CycleProvider>
    </HubPage>
  );
}
