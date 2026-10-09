import { QueryClientProvider } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { BrowserRouter, useRoutes } from "react-router";

import { LoginPage, RequireAuth } from "@/features/auth";
import { SessionProvider, useSession } from "@/shared/session";
import { SlotsProvider } from "@/shared/slots";

import { AppLayout, NotFound } from "./AppLayout";
import { createQueryClient } from "./queryClient";
import { collectSlots, enabledManifests, navItems } from "./registry";

export function AppRoutes() {
  const { features, hasRole } = useSession();
  const enabled = useMemo(() => enabledManifests(features), [features]);
  const slots = useMemo(() => collectSlots(enabled), [enabled]);
  const nav = navItems(enabled, hasRole);
  const routes = useRoutes([
    { path: "/login", element: <LoginPage /> },
    {
      path: "/",
      element: (
        <RequireAuth>
          <AppLayout nav={nav} />
        </RequireAuth>
      ),
      children: [...enabled.flatMap((m) => m.routes ?? []), { path: "*", element: <NotFound /> }],
    },
  ]);
  return <SlotsProvider value={slots}>{routes}</SlotsProvider>;
}

export function App() {
  const [client] = useState(createQueryClient);
  return (
    <QueryClientProvider client={client}>
      <SessionProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </SessionProvider>
    </QueryClientProvider>
  );
}
