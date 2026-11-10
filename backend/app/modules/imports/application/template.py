"""File mẫu nhập hàng loạt (P2-08, v0.15): ZIP gồm manifest.csv mẫu và HUONG-DAN.txt.

Hướng dẫn nằm trong file tải về (không hiện dài trên trang web). CSV và TXT mã hóa UTF-8 có BOM, xuống dòng CRLF để
Excel/Notepad trên Windows mở đúng tiếng Việt. Mã danh mục trong mẫu lấy từ danh mục thật đang dùng.
"""

import io
import zipfile

from sqlalchemy.orm import Session

from app.modules.categories.application import manage as categories

GUIDE = """HƯỚNG DẪN NHẬP HÀNG LOẠT BẰNG manifest.csv
==========================================

1. Cách tải lên
   - Chọn manifest.csv cùng các file cần nhập, HOẶC
   - Nén tất cả vào một file ZIP, đặt manifest.csv ở gốc ZIP.
   Lô không có manifest.csv sẽ bị từ chối (MANIFEST_REQUIRED).

2. Mỗi dòng trong manifest.csv là MỘT tài liệu. Các cột:

   file_name      (bắt buộc) File chính được OCR. Ghi đúng tên file (không phân biệt hoa/thường; trong ZIP chỉ
                  cần tên file, không cần đường dẫn).
                  Ghi nhiều ảnh/PDF, phân cách bằng dấu ; để GỘP thành một tài liệu PDF theo đúng thứ tự đã ghi.
                  Ví dụ: trang-1.jpg;trang-2.jpg;trang-3.jpg
   attachments    Tài liệu đi kèm (không OCR: Word, Excel, PDF, ảnh...), nhiều file phân cách bằng dấu ;
   title          Tiêu đề tài liệu. Khi gộp nhiều file, tên file PDF sau khi gộp cũng lấy theo title.
                  Để trống thì lấy theo tên file đầu tiên trong cột file_name.
   category       Mã danh mục (xem Quản trị > Danh mục). Ưu tiên hơn danh mục chọn cho cả lô trên trang.
   document_code  Số hiệu văn bản.
   validity       Hiệu lực: effective (Còn hiệu lực), effective_until (Còn hiệu lực đến ngày),
                  expired (Hết hiệu lực), unspecified (Không quy định). Để trống = Không quy định.
   valid_until    Ngày hết hiệu lực khi validity = effective_until, dạng 31/12/2027 hoặc 2027-12-31
                  (phải từ hôm nay trở đi).

3. Lưu ý
   - Lưu file dạng CSV UTF-8 (Excel: Lưu thành > CSV UTF-8 (Comma delimited)).
   - File có trong lô nhưng không ghi trong manifest sẽ bị BỎ QUA (báo cáo ghi NOT_IN_MANIFEST).
   - File ghi trong manifest mà không có trong lô, mã danh mục sai, hiệu lực sai: chỉ dòng đó bị lỗi,
     các dòng khác vẫn được nhập.
   - Sau khi nhập, xem kết quả từng tài liệu ở trang Báo cáo lô.
"""


def build_template(db: Session) -> bytes:
    code = next((c.code for c in categories.active_categories(db) if c.code and not c.is_system), None) or "HOP-DONG"
    rows = [
        "file_name,attachments,title,category,document_code,validity,valid_until",
        f"quyet-dinh-12.pdf,phu-luc-1.docx;bang-ke.xlsx,Quyết định số 12/2026,{code},12/QĐ-UBND,effective,",
        "trang-1.jpg;trang-2.jpg;trang-3.jpg,,Biên bản nghiệm thu,,05/BB,effective_until,31/12/2027",
        "scan-001.pdf,,,,,,",
    ]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.csv", ("﻿" + "\r\n".join(rows) + "\r\n").encode("utf-8"))
        zf.writestr("HUONG-DAN.txt", ("﻿" + GUIDE.replace("\n", "\r\n")).encode("utf-8"))
    return buf.getvalue()
