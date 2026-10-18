import { ListTodo } from "lucide-react";

import type { FeatureManifest } from "@/shared/types/feature";

import { JobsPage } from "./JobsPage";

/** FR-11 (v0.7): hàng đợi xử lý - Nghiệp vụ (theo phạm vi) và Admin; server kiểm quyền (GET /api/jobs). */
export const jobsManifest: FeatureManifest = {
  id: "jobs",
  routes: [{ path: "jobs", element: <JobsPage /> }],
  nav: [
    {
      to: "/jobs",
      label: "Hàng đợi xử lý",
      roles: ["OFFICER"],
      group: "documents",
      order: 25,
      icon: ListTodo,
    },
  ],
};
