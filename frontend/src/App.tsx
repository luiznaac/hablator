import type { RouteObject } from "react-router-dom";
import { Layout } from "./components/Layout.tsx";
import { Dashboard } from "./pages/Dashboard.tsx";
import { PrototypeConsole } from "./prototype/PrototypeConsole.tsx";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Layout />,
    children: [{ index: true, element: <Dashboard /> }],
  },
  // Throwaway prototype route (issue #19) — never merges to master as-is.
  { path: "/prototype", element: <PrototypeConsole /> },
];
