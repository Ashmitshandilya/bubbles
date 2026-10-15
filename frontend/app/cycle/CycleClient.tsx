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
        </header>
        <CycleTabs />
      </CycleProvider>
    </HubPage>
  );
}
