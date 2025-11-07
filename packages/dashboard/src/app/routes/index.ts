import { createBrowserRouter } from "react-router-dom";

import Layout from "@/widgets/layout";

export const routes = createBrowserRouter([
  {
    id: "root",
    path: "/",
    Component: Layout,
    shouldRevalidate: () => false, // ограничиваем вызов на изменениях роута
    children: [
      {
        path: "/dashboard",
        async lazy() {
          const { Page } = await import("@/pages/dashboard");

          return {
            Component: Page,
          };
        },
      },
      {
        path: "/settings",
        async lazy() {
          const { Page } = await import("@/pages/settings");

          return {
            Component: Page,
          };
        },
      },
      {
        path: "*",
        async lazy() {
          const { Page } = await import("@/pages/not-found");

          return {
            Component: Page,
          };
        },
      },
    ],
  },
]);

// Используется только во время разработки
if (import.meta.hot) {
  import.meta.hot.dispose(() => routes.dispose());
}
