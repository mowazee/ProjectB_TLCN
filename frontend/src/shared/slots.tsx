/**
 * Slot của UI registry được cấp qua context: app/ gộp manifest đang bật (theo features từ /api/auth/me)
 * rồi đưa xuống; page của feature lõi chỉ đọc useSlots() nên không phải import feature P2 (R9).
 */
import { createContext, Suspense, useContext, type ComponentType, type ReactNode } from "react";

import type { FeatureManifest } from "./types/feature";

export type Slots = Required<
  Pick<
    FeatureManifest,
    | "documentTabs"
    | "documentActions"
    | "pageOverlays"
    | "editorTools"
    | "auditRowActions"
    | "headerItems"
    | "uploadFields"
  >
> & { dashboardCards: NonNullable<FeatureManifest["dashboardCards"]> };

export const EMPTY_SLOTS: Slots = {
  documentTabs: [],
  documentActions: [],
  pageOverlays: [],
  editorTools: [],
  auditRowActions: [],
  headerItems: [],
  uploadFields: [],
  dashboardCards: [],
};

const SlotsContext = createContext<Slots>(EMPTY_SLOTS);

export function SlotsProvider({ value, children }: { value: Slots; children: ReactNode }) {
  return <SlotsContext.Provider value={value}>{children}</SlotsContext.Provider>;
}

export function useSlots(): Slots {
  return useContext(SlotsContext);
}

/** Render danh sách component của một slot (hỗ trợ lazy). */
export function SlotList<P extends object>({ items, props }: { items: ComponentType<P>[]; props: P }) {
  return (
    <Suspense fallback={null}>
      {items.map((C, i) => (
        <C key={i} {...props} />
      ))}
    </Suspense>
  );
}
