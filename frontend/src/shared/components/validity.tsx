/** FR-19 (SDD v0.14, D-14): hiệu lực tài liệu - nhãn và ô chọn dùng chung (gửi duyệt, duyệt, đổi hiệu lực). */
import { Badge } from "@/shared/components/ui";
import { formatValidity, todayISO, VALIDITY_OPTIONS, VALIDITY_TONE } from "@/shared/lib/validity";

export function ValidityBadge({ status, validUntil }: { status?: string | null; validUntil?: string | null }) {
  const st = status ?? "unspecified";
  return <Badge tone={VALIDITY_TONE[st] ?? "neutral"}>{formatValidity(st, validUntil)}</Badge>;
}

export interface ValidityValue {
  status: string | null;
  validUntil: string;
}

export function validityIncomplete(v: ValidityValue): boolean {
  return !v.status || (v.status === "effective_until" && (!v.validUntil || v.validUntil < todayISO()));
}

export function ValidityPicker({
  value,
  onChange,
  name = "validity",
}: {
  value: ValidityValue;
  onChange: (v: ValidityValue) => void;
  name?: string;
}) {
  return (
    <fieldset className="stack" style={{ border: 0, padding: 0, margin: 0 }}>
      <legend>
        <strong>Hiệu lực của tài liệu</strong>
      </legend>
      {VALIDITY_OPTIONS.map((o) => (
        <div key={o.value} className="stack" style={{ gap: 4 }}>
          <label className="row">
            <input
              type="radio"
              name={name}
              checked={value.status === o.value}
              onChange={() => onChange({ ...value, status: o.value })}
            />
            {o.label}
          </label>
          {o.value === "effective_until" && value.status === "effective_until" && (
            <input
              type="date"
              className="input"
              aria-label="Còn hiệu lực đến ngày"
              min={todayISO()}
              value={value.validUntil}
              onChange={(e) => onChange({ ...value, validUntil: e.target.value })}
            />
          )}
        </div>
      ))}
    </fieldset>
  );
}
