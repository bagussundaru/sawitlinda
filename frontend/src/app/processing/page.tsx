import { Suspense } from "react";

import ProcessingScreen from "./ProcessingScreen";

export default function ProsesPage() {
  return (
    <Suspense fallback={<p className="text-sm text-[var(--muted)]">Loading…</p>}>
      <ProcessingScreen />
    </Suspense>
  );
}
