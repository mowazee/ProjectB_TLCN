import { initials } from "@/shared/lib/format";

import s from "./sharing.module.css";

const TONES = ["blue", "violet", "teal", "amber"] as const;

/** Avatar chữ cái đầu; màu cố định theo tên để cùng một người luôn cùng màu. */
export function Avatar({ name }: { name: string }) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const tone = TONES[h % TONES.length];
  return (
    <span className={`${s.avatar} ${s[`av_${tone}`]}`} aria-hidden>
      {initials(name)}
    </span>
  );
}
