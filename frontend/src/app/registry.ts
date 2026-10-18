/**
 * UI registry (Đặc tả đề tài v0.5 mục 4.3, 4.6): danh sách manifest; feature P2/P3 chỉ thêm MỘT dòng.
 * Manifest có `feature` chỉ bật khi cờ nằm trong session.features (GET /api/auth/me).
 */
import { accountManifest } from "@/features/account";
import { adminManifest } from "@/features/admin";
import { borrowingManifest } from "@/features/borrowing";
import { classificationManifest } from "@/features/classification";
import { dashboardManifest } from "@/features/dashboard";
import { documentsManifest } from "@/features/documents";
import { extractionManifest } from "@/features/extraction";
import { handwritingManifest } from "@/features/handwriting";
import { highlightManifest } from "@/features/highlight";
import { importsManifest } from "@/features/imports";
import { notificationsManifest } from "@/features/notifications";
import { ocrManifest } from "@/features/ocr";
import { rollbackManifest } from "@/features/rollback";
import { searchManifest } from "@/features/search";
import { versionsManifest } from "@/features/versions";
import { workflowManifest } from "@/features/workflow";
import { EMPTY_SLOTS, type Slots } from "@/shared/slots";
import type { FeatureManifest, NavItem } from "@/shared/types/feature";

export type { FeatureManifest } from "@/shared/types/feature";

export const manifests: FeatureManifest[] = [
  dashboardManifest,
  documentsManifest,
  ocrManifest,
  searchManifest,
  adminManifest, // lõi MVP
  accountManifest, // FR-09 (v0.7)
  workflowManifest, // P2-01
  highlightManifest, // P2-02
  handwritingManifest, // P2-03
  extractionManifest, // P2-04
  classificationManifest, // P2-05
  versionsManifest, // P2-06
  borrowingManifest, // P2-07
  notificationsManifest, // P2-07
  importsManifest, // P2-08
  rollbackManifest, // P2-09
];

export function enabledManifests(features: readonly string[], all: FeatureManifest[] = manifests): FeatureManifest[] {
  return all.filter((m) => !m.feature || features.includes(m.feature));
}

export function collectSlots(enabled: FeatureManifest[]): Slots {
  const slots: Slots = {
    documentTabs: [],
    documentActions: [],
    pageOverlays: [],
    editorTools: [],
    auditRowActions: [],
    headerItems: [],
    uploadFields: [],
    dashboardCards: [],
  };
  for (const m of enabled) {
    for (const key of Object.keys(EMPTY_SLOTS) as (keyof Slots)[]) {
      const items = m[key];
      if (items) (slots[key] as unknown[]).push(...items);
    }
  }
  return slots;
}

export function navItems(enabled: FeatureManifest[], hasRole: (...roles: string[]) => boolean): NavItem[] {
  return enabled
    .flatMap((m) => m.nav ?? [])
    .filter((n) => !n.roles || hasRole(...n.roles))
    .sort((a, b) => (a.order ?? 50) - (b.order ?? 50));
}
