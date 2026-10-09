"""P2-06 so sánh phiên bản (UC-12) và P2-02 highlight trên ảnh trang (UC-19)."""

from app.modules.ocr.domain.diff import diff_text
from app.modules.search.domain import highlight
from tests.conftest import make_pdf, make_png, run_all_jobs, upload

F = "versions,highlight"


def _processed(seed, login, enqueued, data=None, name="a.png"):
    c = login("officer", features=F)
    doc_id = upload(c, seed["category"].id, data or make_png(), name).json()["document_id"]
    run_all_jobs(enqueued)
    return c, doc_id


def test_diff_unit():
    d = diff_text("Hop dong so 1\nCong ty ABC\nKy ten", "Hop dong so 1\nCong ty XYZ\nKy ten\nDong dau")
    ops = [h.op for h in d.hunks]
    assert ops == ["equal", "replace", "equal", "insert"] and d.lines_added == 2 and d.lines_removed == 1
    words = [(w.op, w.old, w.new) for w in d.hunks[1].words]
    assert ("replace", "ABC", "XYZ") in words
    assert diff_text("a\nb", "a\nb").identical


def test_versions_list_and_diff(seed, login, fake_engine, enqueued):
    c, doc_id = _processed(seed, login, enqueued)
    raw = c.get(f"/api/documents/{doc_id}/pages/1").json()["raw_text"]
    c.put(
        f"/api/documents/{doc_id}/pages/1/correction",
        json={"corrected_text": raw.replace("ABC", "XYZ"), "base_version": 0},
    )
    versions = c.get(f"/api/documents/{doc_id}/pages/1/versions").json()
    assert [(v["version"], v["is_raw"]) for v in versions] == [(0, True), (1, False)]
    assert versions[0]["engine_version"] == "fake 1.0" and versions[1]["edited_by_name"] == "Officer"
    d = c.get(f"/api/documents/{doc_id}/pages/1/versions/diff", params={"from": 0, "to": 1}).json()
    assert d["identical"] is False and d["lines_added"] == 1 and d["lines_removed"] == 1
    replace = next(h for h in d["hunks"] if h["op"] == "replace")
    assert {"op": "replace", "old": "ABC", "new": "XYZ"} in replace["words"]
    assert c.get(f"/api/documents/{doc_id}/pages/1/versions/diff", params={"from": 0, "to": 5}).status_code == 404
    assert login("officerb", features=F).get(f"/api/documents/{doc_id}/pages/1/versions").status_code == 403
    assert login("officer", features="").get(f"/api/documents/{doc_id}/pages/1/versions").status_code == 404


def test_highlight_unit_reasons():
    boxes = [
        {"text": "Hợp đồng số 1", "score": 0.9, "box": [10, 10, 130, 20]},
        {"text": "Công ty ABC, công ty XYZ", "score": 0.9, "box": [10, 40, 240, 20]},
    ]
    raw = "Hợp đồng số 1\nCông ty ABC, công ty XYZ"
    found, reason = highlight.compute("CONG TY", boxes, effective_text=raw, raw_text=raw)
    assert reason is None and [(b.line, b.start, b.end) for b in found] == [(1, 0, 7), (1, 13, 20)]
    assert found[0].x == 10 and found[0].w == 70 and found[1].x == 140  # theo tỉ lệ ký tự
    assert highlight.compute(" ", boxes, effective_text=raw, raw_text=raw) == ([], highlight.EMPTY_QUERY)
    assert highlight.compute("abc", boxes, effective_text="đã sửa", raw_text=raw) == ([], highlight.TEXT_MODIFIED)
    assert highlight.compute("khong co", boxes, effective_text=raw, raw_text=raw) == ([], highlight.NOT_FOUND)
    no_box = [{"text": "Hợp đồng", "score": None, "box": [0, 0, 0, 0]}]
    assert highlight.compute("hop", no_box, effective_text="Hợp đồng", raw_text="Hợp đồng")[1] == highlight.NO_BOXES


def test_highlight_api(seed, login, fake_engine, enqueued):
    c, doc_id = _processed(seed, login, enqueued)
    h = c.get(f"/api/documents/{doc_id}/pages/1/highlights", params={"q": "cong ty"}).json()
    assert h["total"] == 1 and h["reason"] is None and h["width"] > 0
    assert h["boxes"][0] == {"x": 20, "y": 60, "w": 109, "h": 30, "line": 1}  # "Cong ty TNHH ABC" 7/16
    c.put(f"/api/documents/{doc_id}/pages/1/correction", json={"corrected_text": "khác", "base_version": 0})
    h = c.get(f"/api/documents/{doc_id}/pages/1/highlights", params={"q": "cong ty"}).json()
    assert h["boxes"] == [] and h["reason"] == "text_modified"
    assert login("officerb", features=F).get(f"/api/documents/{doc_id}/pages/1/highlights?q=a").status_code == 403


def test_highlight_on_pdf_text_layer(seed, login, fake_engine, enqueued):
    c, doc_id = _processed(seed, login, enqueued, make_pdf(["Biên bản nghiệm thu công trình số 7"]), "bb.pdf")
    h = c.get(f"/api/documents/{doc_id}/pages/1/highlights", params={"q": "nghiem thu"}).json()
    assert h["total"] == 1 and h["boxes"][0]["w"] > 0
    assert fake_engine.calls == 0
