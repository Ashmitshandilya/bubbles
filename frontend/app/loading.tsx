import { Skeleton } from "../components/hub/HubKit";

export default function Loading() {
  return (
    <main role="status" className="mx-auto w-full max-w-content space-y-3 px-gutter py-6">
      <span className="sr-only">Loading</span>
      <Skeleton className="h-24 rounded-3xl" />
      <Skeleton className="h-24 rounded-3xl" />
      <Skeleton className="h-24 rounded-3xl" />
    </main>
  );
}
