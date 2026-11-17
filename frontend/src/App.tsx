import type { RouteObject } from "react-router-dom";
import { Layout } from "./components/Layout.tsx";
import { Console } from "./pages/Console.tsx";

export const routes: RouteObject[] = [
  {
    path: "/",
    element: <Layout />,
    children: [{ index: true, element: <Console /> }],
  },
];
