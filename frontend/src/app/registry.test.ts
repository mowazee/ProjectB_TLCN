import { describe, expect, it } from "vitest";

import { collectSlots, enabledManifests, manifests, navItems } from "./registry";

const ids = (features: string[]) => enabledManifests(features).map((m) => m.id);

describe("UI registry (NFR-09)", () => {
  it("chỉ bật manifest P2 khi cờ có trong session.features", () => {
    expect(ids([])).toEqual(["dashboard", "documents", "ocr", "search", "admin", "account"]);
    expect(ids(["workflow"])).toContain("workflow");
    expect(ids(["workflow"])).not.toContain("borrowing");
    expect(ids(manifests.flatMap((m) => (m.feature ? [m.feature] : []))).length).toBe(manifests.length);
  });

  it("gộp slot từ manifest đang bật", () => {
    const off = collectSlots(enabledManifests([]));
    expect(off.documentTabs).toHaveLength(0);
    expect(off.pageOverlays).toHaveLength(0);
    const on = collectSlots(
      enabledManifests(["highlight", "extraction", "classification", "versions", "notifications"]),
    );
    expect(on.pageOverlays).toHaveLength(1);
    expect(on.documentTabs.map((t) => t.id)).toEqual(["fields", "suggestions"]);
    expect(on.editorTools).toHaveLength(1);
    expect(on.headerItems).toHaveLength(1);
  });

  it("menu lọc theo vai trò (server vẫn kiểm quyền)", () => {
    const enabled = enabledManifests(["workflow", "imports"]);
    const officer = navItems(enabled, (...r) => r.includes("OFFICER")).map((n) => n.to);
    const approver = navItems(enabled, (...r) => r.includes("APPROVER")).map((n) => n.to);
    expect(officer).toContain("/imports");
    expect(officer).not.toContain("/reviews");
    expect(officer).not.toContain("/admin/users");
    expect(approver).toContain("/reviews");
    expect(officer[0]).toBe("/");
  });
});
