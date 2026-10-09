import { ErrorBox, JobBadge, ProgressBar } from "@/shared/components/ui";
import type { Job } from "@/shared/api/types";

import { useJob, useRetryJob } from "./useJob";

/** Tiến độ một job: badge + thanh tiến độ + lỗi an toàn + nút retry (job failed, người có quyền). */
export function JobStatus({
  jobId,
  canRetry,
  onDone,
}: {
  jobId: string;
  canRetry?: boolean;
  onDone?: (job: Job) => void;
}) {
  const { data: job, error } = useJob(jobId, onDone);
  const retry = useRetryJob();
  if (error) return <ErrorBox error={error} />;
  if (!job) return null;
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row">
        <span className="muted">Job {job.kind}</span>
        <JobBadge status={job.status} />
        <span className="muted">
          lần {job.attempt}/{job.max_attempts}
        </span>
        {job.status === "failed" && canRetry && (
          <button className="btn btn-sm" onClick={() => retry.mutate(job.id)} disabled={retry.isPending}>
            Chạy lại
          </button>
        )}
      </div>
      {(job.status === "processing" || job.status === "queued") && <ProgressBar value={job.progress} />}
      {job.status === "failed" && job.error_message && (
        <span style={{ color: "var(--c-danger)" }}>
          {job.error_message} ({job.error_code})
        </span>
      )}
      <ErrorBox error={retry.error} />
    </div>
  );
}
