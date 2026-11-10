import { describe, expect, it } from "vitest";

import {
  History,
  countMatches,
  diffLines,
  findNext,
  isLow,
  lineIndexAt,
  lineRange,
  locateBox,
  matchBox,
  replaceAll,
} from "./editorUtils";

const BOXES = [
  { text: "CỘNG HÒA XÃ HỘI", score: 0.98, box: [10, 10, 200, 20] },
  { text: "Quyết đinh số 12", score: 0.55, box: [10, 40, 180, 20] },
  { text: "Điều 1", score: 92, box: [10, 70, 60, 20] },
];

describe("editorUtils (FR-05 mức 1)", () => {
  it("ánh xạ dòng đang sửa về box cùng nội dung; dòng đã đổi thì không tô sáng", () => {
    const text = "CỘNG HÒA XÃ HỘI\nQuyết đinh số 12\nĐiều 1";
    expect(lineIndexAt(text, text.indexOf("Quyết"))).toBe(1);
    expect(lineRange(text, 2)).toEqual([text.indexOf("Điều"), text.length]);
    expect(matchBox(text, 1, BOXES)).toBe(1);
    const edited = "CỘNG HÒA XÃ HỘI\nQuyết định số 12\nĐiều 1";
    expect(matchBox(edited, 1, BOXES)).toBeNull();
    expect(matchBox("Dòng mới\n" + text, 3, BOXES)).toBe(2);
  });

  it("độ tin cậy thấp dùng thang 0-1 hoặc 0-100", () => {
    expect(BOXES.map(isLow)).toEqual([false, true, false]);
    expect(isLow({ text: "x", score: null, box: [] })).toBe(false);
    const text = "a\nQuyết đinh số 12";
    expect(locateBox(text, BOXES, 1)).toEqual([2, text.length]);
  });

  it("tìm, đếm, thay thế không phân biệt hoa thường và ký tự đặc biệt", () => {
    const t = "Hop dong (1) - HOP DONG";
    expect(countMatches(t, "hop dong", false)).toBe(2);
    expect(countMatches(t, "hop dong", true)).toBe(0);
    expect(findNext(t, "(1)", 0, false)).toEqual([9, 12]);
    expect(findNext(t, "hop", 5, false)).toEqual([15, 18]);
    expect(findNext(t, "hop", 20, false)).toEqual([0, 3]);
    expect(replaceAll(t, "hop dong", "Hợp đồng", false)).toBe("Hợp đồng (1) - Hợp đồng");
    expect(replaceAll(t, "$", "x", false)).toBe(t);
  });

  it("diff theo dòng và lịch sử hoàn tác", () => {
    expect(diffLines("a\nb\nc", "a\nB\nc")).toEqual([
      { kind: "same", text: "a" },
      { kind: "del", text: "b" },
      { kind: "add", text: "B" },
      { kind: "same", text: "c" },
    ]);
    const h = new History(2);
    h.push("1");
    h.push("2");
    h.push("3");
    expect(h.undo("4")).toBe("3");
    expect(h.undo("3")).toBe("2");
    expect(h.undo("2")).toBeNull();
    expect(h.redo("2")).toBe("3");
  });
});
