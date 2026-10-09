import { useState, type FormEvent } from "react";

import type { StorageLocation } from "@/shared/api/types";
import {
  EmptyState,
  ErrorBox,
  Field,
  Loading,
  Modal,
  PageHeader,
  Pagination,
  fieldErrors,
} from "@/shared/components/ui";
import { useSession } from "@/shared/session";
import type { DocumentSlotProps } from "@/shared/types/feature";

import {
  useBorrowMutations,
  useBorrows,
  useDocLocation,
  useLocations,
  useSaveLocation,
  useSetDocLocation,
} from "./api";
import { BorrowTable } from "./BorrowTable";

/** UC-11, UC-16 (P2-07): danh sách yêu cầu mượn; Kiểm duyệt thấy yêu cầu trong phạm vi, người khác thấy của mình. */
export function BorrowRequestsPage() {
  const { hasRole } = useSession();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [mine, setMine] = useState(!hasRole("APPROVER"));
  const list = useBorrows({ page, status, overdue, mine });
  return (
    <div>
      <PageHeader title="Mượn hồ sơ" subtitle="Tạo yêu cầu mượn từ trang chi tiết tài liệu (tab “Mượn hồ sơ”)." />
      <div className="row" style={{ marginBottom: 12 }}>
        <select
          className="select"
          style={{ maxWidth: 200 }}
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
          aria-label="Trạng thái"
        >
          <option value="">Mọi trạng thái</option>
          <option value="pending">Chờ duyệt</option>
          <option value="approved">Đang mượn</option>
          <option value="rejected">Từ chối</option>
          <option value="returned">Đã trả</option>
        </select>
        <label className="row">
          <input
            type="checkbox"
            checked={overdue}
            onChange={(e) => {
              setOverdue(e.target.checked);
              setPage(1);
            }}
          />{" "}
          Chỉ quá hạn
        </label>
        {hasRole("APPROVER") && (
          <label className="row">
            <input
              type="checkbox"
              checked={mine}
              onChange={(e) => {
                setMine(e.target.checked);
                setPage(1);
              }}
            />{" "}
            Chỉ yêu cầu của tôi
          </label>
        )}
      </div>
      <ErrorBox error={list.error} />
      {list.isPending ? (
        <Loading />
      ) : !list.data?.items.length ? (
        <EmptyState>Không có yêu cầu mượn.</EmptyState>
      ) : (
        <>
          <BorrowTable items={list.data.items} />
          <Pagination page={page} pageSize={list.data.page_size} total={list.data.total} onChange={setPage} />
        </>
      )}
    </div>
  );
}

/** Tab trên tài liệu: vị trí bản cứng + tạo yêu cầu mượn + các yêu cầu của hồ sơ. */
export function BorrowTab({ document }: DocumentSlotProps) {
  const location = useDocLocation(document.id);
  const locations = useLocations();
  const setLocation = useSetDocLocation(document.id);
  const { create } = useBorrowMutations();
  const list = useBorrows({ page: 1, document_id: document.id });
  const today = new Date().toISOString().slice(0, 10);
  const [form, setForm] = useState({ from_date: today, to_date: today, purpose: "" });
  const errors = fieldErrors(create.error);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(
      { document_id: document.id, ...form, purpose: form.purpose.trim() || null },
      { onSuccess: () => setForm({ from_date: today, to_date: today, purpose: "" }) },
    );
  };

  if (location.isPending) return <Loading />;
  const loc = location.data?.storage_location ?? null;
  return (
    <div className="stack">
      <div className="row">
        <strong>Vị trí bản cứng:</strong>
        {document.can_edit ? (
          <select
            className="select"
            style={{ maxWidth: 280 }}
            value={loc?.id ?? ""}
            onChange={(e) => setLocation.mutate(e.target.value ? Number(e.target.value) : null)}
            aria-label="Vị trí lưu trữ"
          >
            <option value="">— Chưa có —</option>
            {locations.data?.map((l) => (
              <option key={l.id} value={l.id}>
                {l.code} - {l.name}
              </option>
            ))}
          </select>
        ) : (
          <span>{loc ? `${loc.code} - ${loc.name}` : "Chưa có"}</span>
        )}
      </div>
      <ErrorBox error={setLocation.error} />
      {loc && (
        <form className="row" onSubmit={submit} style={{ alignItems: "flex-end" }}>
          <Field label="Từ ngày" htmlFor="fd" error={errors.from_date}>
            <input
              id="fd"
              className="input"
              type="date"
              value={form.from_date}
              min={today}
              onChange={(e) => setForm({ ...form, from_date: e.target.value })}
              required
            />
          </Field>
          <Field label="Đến ngày" htmlFor="td" error={errors.to_date}>
            <input
              id="td"
              className="input"
              type="date"
              value={form.to_date}
              min={form.from_date}
              onChange={(e) => setForm({ ...form, to_date: e.target.value })}
              required
            />
          </Field>
          <div className="grow">
            <Field label="Mục đích" htmlFor="pp">
              <input
                id="pp"
                className="input"
                value={form.purpose}
                onChange={(e) => setForm({ ...form, purpose: e.target.value })}
              />
            </Field>
          </div>
          <button className="btn btn-primary" type="submit" disabled={create.isPending}>
            Tạo yêu cầu mượn
          </button>
        </form>
      )}
      <ErrorBox error={create.error} />
      {list.data && list.data.items.length > 0 && <BorrowTable items={list.data.items} showDocument={false} />}
    </div>
  );
}

function LocationForm({ loc, onClose }: { loc: StorageLocation | null; onClose: () => void }) {
  const save = useSaveLocation();
  const [name, setName] = useState(loc?.name ?? "");
  const [code, setCode] = useState(loc?.code ?? "");
  const errors = fieldErrors(save.error);
  return (
    <Modal
      title={loc ? "Sửa vị trí lưu trữ" : "Thêm vị trí lưu trữ"}
      onClose={onClose}
      actions={
        <button
          className="btn btn-primary"
          disabled={save.isPending}
          onClick={() => save.mutate({ id: loc?.id, name, code }, { onSuccess: onClose })}
        >
          Lưu
        </button>
      }
    >
      <div className="stack">
        <ErrorBox error={save.error} />
        <Field label="Mã" htmlFor="lc" error={errors.code} hint="Chữ, số, - _ .">
          <input id="lc" className="input" value={code} onChange={(e) => setCode(e.target.value)} />
        </Field>
        <Field label="Tên" htmlFor="ln" error={errors.name}>
          <input id="ln" className="input" value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
      </div>
    </Modal>
  );
}

export function StorageLocationsPage() {
  const locations = useLocations();
  const [editing, setEditing] = useState<StorageLocation | null | "new">(null);
  return (
    <div>
      <PageHeader
        title="Kho lưu trữ hồ sơ"
        actions={
          <button className="btn btn-primary" onClick={() => setEditing("new")}>
            + Thêm vị trí
          </button>
        }
      />
      <ErrorBox error={locations.error} />
      {locations.isPending ? (
        <Loading />
      ) : !locations.data?.length ? (
        <EmptyState>Chưa có vị trí lưu trữ.</EmptyState>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Mã</th>
              <th>Tên</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {locations.data.map((l) => (
              <tr key={l.id}>
                <td>{l.code}</td>
                <td>{l.name}</td>
                <td>
                  <button className="btn btn-sm" onClick={() => setEditing(l)}>
                    Sửa
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && <LocationForm loc={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}
