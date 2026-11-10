/** Hàm thuần cho OCR Editor mức 1 (FR-05, SDD v0.13): ánh xạ dòng ↔ box, độ tin cậy thấp, tìm/thay thế, diff. */

export interface LineBox {
  text: string;
  score: number | null;
  box: number[];
}

/** Ngưỡng tin cậy thấp: score của engine trong [0, 1] (hoặc [0, 100] với engine cũ). */
export const LOW_SCORE = 0.8;

export function normalizeScore(score: number | null): number | null {
  if (score === null || Number.isNaN(score)) return null;
  return score > 1 ? score / 100 : score;
}

export function isLow(box: LineBox): boolean {
  const s = normalizeScore(box.score);
  return s !== null && s < LOW_SCORE;
}

/** Chỉ số dòng (0-based) chứa vị trí con trỏ. */
export function lineIndexAt(text: string, pos: number): number {
  let n = 0;
  for (let i = 0; i < Math.min(pos, text.length); i++) if (text[i] === "\n") n++;
  return n;
}

/** [start, end) của dòng thứ index. */
export function lineRange(text: string, index: number): [number, number] {
  let start = 0;
  for (let i = 0; i < index; i++) {
    const nl = text.indexOf("\n", start);
    if (nl < 0) return [text.length, text.length];
    start = nl + 1;
  }
  const end = text.indexOf("\n", start);
  return [start, end < 0 ? text.length : end];
}

const norm = (s: string) => s.replace(/\s+/g, " ").trim();

/**
 * Box ứng với dòng index của bản đang sửa: box có cùng nội dung (bỏ khác biệt khoảng trắng), gần vị trí dòng nhất.
 * Dòng đã bị sửa/thêm/bớt so với bản OCR thì không có box → không tô sáng sai (SDD v0.13 FR-05).
 */
export function matchBox(text: string, index: number, boxes: LineBox[]): number | null {
  const [a, b] = lineRange(text, index);
  const line = norm(text.slice(a, b));
  if (!line) return null;
  let best: number | null = null;
  boxes.forEach((bx, k) => {
    if (norm(bx.text) === line && (best === null || Math.abs(k - index) < Math.abs(best - index))) best = k;
  });
  return best;
}

/** Vị trí [start, end) trong text của dòng có nội dung bằng box k (dùng khi nhảy tới dòng tin cậy thấp). */
export function locateBox(text: string, boxes: LineBox[], k: number): [number, number] | null {
  const target = norm(boxes[k].text);
  const lines = text.split("\n");
  let pos = 0;
  let best: [number, number] | null = null;
  let bestDist = Infinity;
  lines.forEach((ln, i) => {
    if (norm(ln) === target && Math.abs(i - k) < bestDist) {
      best = [pos, pos + ln.length];
      bestDist = Math.abs(i - k);
    }
    pos += ln.length + 1;
  });
  return best;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function findNext(text: string, query: string, from: number, matchCase: boolean): [number, number] | null {
  if (!query) return null;
  const re = new RegExp(escapeRegExp(query), matchCase ? "g" : "gi");
  re.lastIndex = from;
  let m = re.exec(text);
  if (!m && from > 0) {
    re.lastIndex = 0;
    m = re.exec(text);
  }
  return m ? [m.index, m.index + m[0].length] : null;
}

export function countMatches(text: string, query: string, matchCase: boolean): number {
  if (!query) return 0;
  return (text.match(new RegExp(escapeRegExp(query), matchCase ? "g" : "gi")) ?? []).length;
}

export function replaceAll(text: string, query: string, replacement: string, matchCase: boolean): string {
  if (!query) return text;
  return text.replace(new RegExp(escapeRegExp(query), matchCase ? "g" : "gi"), () => replacement);
}

export type DiffOp = { kind: "same" | "add" | "del"; text: string };

/** Diff theo dòng (LCS) giữa bản OCR thô và bản đang sửa; đủ nhanh cho một trang. */
export function diffLines(before: string, after: string): DiffOp[] {
  const a = before.split("\n");
  const b = after.split("\n");
  const dp: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: DiffOp[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ kind: "same", text: a[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ kind: "del", text: a[i++] });
    else out.push({ kind: "add", text: b[j++] });
  }
  while (i < a.length) out.push({ kind: "del", text: a[i++] });
  while (j < b.length) out.push({ kind: "add", text: b[j++] });
  return out;
}

/** Lịch sử hoàn tác/làm lại (giới hạn để không phình bộ nhớ). */
export class History {
  private past: string[] = [];
  private future: string[] = [];
  constructor(private readonly limit = 200) {}
  push(previous: string) {
    this.past.push(previous);
    if (this.past.length > this.limit) this.past.shift();
    this.future = [];
  }
  undo(current: string): string | null {
    const prev = this.past.pop();
    if (prev === undefined) return null;
    this.future.push(current);
    return prev;
  }
  redo(current: string): string | null {
    const next = this.future.pop();
    if (next === undefined) return null;
    this.past.push(current);
    return next;
  }
  get canUndo() {
    return this.past.length > 0;
  }
  get canRedo() {
    return this.future.length > 0;
  }
}
