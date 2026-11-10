"""Job worker cho process demo và to-be.

Chạy:  python src/worker.py      (Ctrl+C để dừng)
"""
import time
import uuid
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from html import escape
from pathlib import Path
from urllib.parse import quote

import camunda_api as api
from sample_db import tra_cuu
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from dotenv import load_dotenv

WORKER = "nhom16-worker"
ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _register_pdf_font() -> str:
    """Register a Unicode font so Vietnamese text renders in the certificate."""
    font_setting = os.getenv("CAMUNDA_PDF_FONT")
    candidates = ([(Path(font_setting), None)] if font_setting else []) + [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("C:/Windows/Fonts/segoeui.ttf"), Path("C:/Windows/Fonts/segoeuib.ttf")),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
         Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
         Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
    ]
    for font_path, bold_path in candidates:
        if font_path.is_file():
            pdfmetrics.registerFont(TTFont("CertificateUnicode", str(font_path)))
            if bold_path and bold_path.is_file():
                pdfmetrics.registerFont(TTFont("CertificateUnicode-Bold", str(bold_path)))
            else:
                pdfmetrics.registerFont(TTFont("CertificateUnicode-Bold", str(font_path)))
            pdfmetrics.registerFontFamily("CertificateUnicode", normal="CertificateUnicode",
                                          bold="CertificateUnicode-Bold", italic="CertificateUnicode",
                                          boldItalic="CertificateUnicode-Bold")
            return "CertificateUnicode"
    raise FileNotFoundError(
        "Không tìm thấy font Unicode để xuất tiếng Việt. Cài Arial/DejaVu Sans hoặc "
        "đặt CAMUNDA_PDF_FONT trỏ tới file .ttf."
    )


def _draw_paragraph(pdf: canvas.Canvas, text: str, x: float, y: float, width: float,
                    style: ParagraphStyle, markup: bool = False) -> float:
    paragraph = Paragraph(text if markup else escape(text), style)
    _, height = paragraph.wrap(width, A4[1])
    paragraph.drawOn(pdf, x, y - height)
    return y - height


def handle_tra_cuu(variables: dict) -> dict:
    mssv = str(variables.get("mssv", "")).strip()
    kq = tra_cuu(mssv, str(variables.get("mucDich", "")))
    print(f"  tra-cuu-mssv: {mssv} -> {kq}")
    return kq


def handle_gui_ket_qua(variables: dict) -> dict:
    # Job gui-ket-qua chỉ dùng trong process demo cũ.
    so = f"XN-{datetime.now():%Y%m%d%H%M%S}"
    print(f"  gui-ket-qua: cấp giấy {so} cho {variables.get('hoTen')} ({variables.get('mssv')})")
    return {"soGiay": so, "ngayCap": datetime.now().isoformat(timespec="seconds")}


def handle_sinh_pdf(variables: dict) -> dict:
    now = datetime.now()
    so = f"XN-{now:%Y%m%d%H%M%S}-{uuid.uuid4().hex[:6].upper()}"
    ma = uuid.uuid4().hex[:12].upper()
    verify_base = os.getenv("CERTIFICATE_VERIFY_BASE_URL", "").strip().rstrip("/")
    qr_payload = f"{verify_base}/{quote(ma)}" if verify_base else f"Ma xac thuc giay: {ma}"
    output_dir = Path(os.getenv("PDF_OUTPUT_DIR", str(ROOT / "generated" / "pdf"))).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = (output_dir / f"{so}.pdf").resolve()

    font_name = _register_pdf_font()
    pdf = canvas.Canvas(str(pdf_path), pagesize=A4)
    page_width, page_height = A4
    pdf.setTitle(f"Giấy xác nhận sinh viên {so}")
    pdf.setAuthor("Hệ thống cấp giấy xác nhận sinh viên UET (bản demo)")
    navy = colors.HexColor("#17365D")
    blue = colors.HexColor("#2F6B9A")
    pale = colors.HexColor("#F3F7FB")
    ink = colors.HexColor("#263445")
    muted = colors.HexColor("#647386")
    title_style = ParagraphStyle("CertificateTitle", fontName=font_name, fontSize=21,
                                 leading=27, alignment=TA_CENTER, textColor=navy)
    subtitle_style = ParagraphStyle("CertificateSubtitle", fontName=font_name, fontSize=10,
                                    leading=14, alignment=TA_CENTER, textColor=muted)
    body_style = ParagraphStyle("CertificateBody", fontName=font_name, fontSize=11,
                                leading=16, alignment=TA_LEFT, textColor=ink)
    label_style = ParagraphStyle("CertificateLabel", fontName=font_name, fontSize=9,
                                 leading=13, alignment=TA_LEFT, textColor=blue)
    note_style = ParagraphStyle("CertificateNote", fontName=font_name, fontSize=9,
                                leading=14, alignment=TA_LEFT, textColor=muted)
    small_style = ParagraphStyle("CertificateSmall", fontName=font_name, fontSize=8,
                                 leading=12, alignment=TA_LEFT, textColor=muted)

    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    pdf.setStrokeColor(colors.HexColor("#C9D6E2"))
    pdf.setLineWidth(0.8)
    pdf.roundRect(32, 32, page_width - 64, page_height - 64, 10, stroke=1, fill=0)

    # Compact institutional header and certificate reference.
    pdf.setFillColor(navy)
    pdf.circle(83, 766, 22, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont(font_name, 10)
    pdf.drawCentredString(83, 762, "UET")
    pdf.setFillColor(navy)
    pdf.setFont(font_name, 10)
    pdf.drawCentredString(page_width / 2 + 20, 780, "ĐẠI HỌC QUỐC GIA HÀ NỘI")
    pdf.setFont(font_name, 12)
    pdf.drawCentredString(page_width / 2 + 20, 760, "TRƯỜNG ĐẠI HỌC CÔNG NGHỆ")
    pdf.setStrokeColor(blue)
    pdf.setLineWidth(1.4)
    pdf.line(58, 727, page_width - 58, 727)

    _draw_paragraph(pdf, "GIẤY XÁC NHẬN SINH VIÊN", 58, 704, page_width - 116, title_style)
    _draw_paragraph(pdf, "XÁC NHẬN THÔNG TIN SINH VIÊN", 58, 678, page_width - 116, subtitle_style)

    issued = now.strftime("%d/%m/%Y")
    pdf.setFillColor(muted)
    pdf.setFont(font_name, 9)
    pdf.drawString(60, 636, f"Số giấy: {so}")
    pdf.drawRightString(page_width - 60, 636, f"Ngày cấp: {issued}")
    pdf.setStrokeColor(colors.HexColor("#E0E7EE"))
    pdf.setLineWidth(0.6)
    pdf.line(60, 622, page_width - 60, 622)

    pdf.setFillColor(ink)
    pdf.setFont(font_name, 11)
    pdf.drawString(60, 596, "Nhà trường xác nhận thông tin của sinh viên như sau:")
    details = [
        ("Họ và tên", str(variables.get("hoTen", ""))),
        ("Mã số sinh viên", str(variables.get("mssv", ""))),
        ("Tình trạng học tập", str(variables.get("trangThaiHocTap", "Đang học"))),
        ("Mục đích", str(variables.get("mucDich", ""))),
    ]
    row_x, row_width, label_width = 60, page_width - 120, 145
    y = 578
    for label, value in details:
        label_paragraph = Paragraph(f"<b>{escape(label.upper())}</b>", label_style)
        value_paragraph = Paragraph(escape(value or "—"), body_style)
        _, label_height = label_paragraph.wrap(label_width - 24, page_height)
        _, value_height = value_paragraph.wrap(row_width - label_width - 28, page_height)
        row_height = max(42, label_height + 20, value_height + 20)
        row_bottom = y - row_height
        pdf.setFillColor(pale)
        pdf.roundRect(row_x, row_bottom, row_width, row_height, 5, stroke=0, fill=1)
        label_paragraph.drawOn(pdf, row_x + 12, row_bottom + (row_height - label_height) / 2)
        value_paragraph.drawOn(pdf, row_x + label_width, row_bottom + (row_height - value_height) / 2)
        y = row_bottom - 9

    y -= 4
    _draw_paragraph(pdf, "Giấy xác nhận được cấp dưới dạng điện tử. Mã QR và mã xác thực "
                    "được dùng để đối chiếu thông tin trên giấy.", 60, y, page_width - 120, note_style)

    verify_box_x, verify_box_y = 60, 108
    verify_box_width, verify_box_height = page_width - 120, 145
    pdf.setFillColor(pale)
    pdf.roundRect(verify_box_x, verify_box_y, verify_box_width, verify_box_height,
                  7, stroke=0, fill=1)
    pdf.setFillColor(blue)
    pdf.setFont("CertificateUnicode-Bold", 9)
    pdf.drawString(78, 226, "XÁC THỰC VĂN BẢN")
    pdf.setFillColor(muted)
    pdf.setFont(font_name, 8)
    pdf.drawString(78, 207, "Mã xác thực")
    pdf.setFillColor(navy)
    pdf.setFont("CertificateUnicode-Bold", 13)
    pdf.drawString(78, 185, ma)
    _draw_paragraph(pdf, "Quét mã QR để đối chiếu giấy xác nhận.", 78, 170,
                    280, small_style)

    qr = QrCodeWidget(qr_payload)
    x1, y1, x2, y2 = qr.getBounds()
    qr_size = 88
    drawing = Drawing(qr_size, qr_size, transform=[qr_size / (x2 - x1), 0, 0,
                                                   qr_size / (y2 - y1), 0, 0])
    drawing.add(qr)
    qr_x = page_width - 78 - qr_size
    qr_y = 137
    renderPDF.draw(drawing, pdf, qr_x, qr_y)
    pdf.setFillColor(muted)
    pdf.setFont(font_name, 8)
    pdf.drawCentredString(qr_x + qr_size / 2, 122, "MÃ QR")
    pdf.setStrokeColor(colors.HexColor("#E0E7EE"))
    pdf.line(60, 80, page_width - 60, 80)
    _draw_paragraph(pdf, "Văn bản điện tử được tạo tự động từ hệ thống cấp giấy xác nhận sinh viên.",
                    60, 68, page_width - 120, small_style)
    pdf.save()

    print(f"  sinh-giay-pdf: đã tạo {pdf_path} (số {so}, mã {ma})")
    return {"soGiay": so, "maXacThuc": ma, "ngayCap": now.isoformat(timespec="seconds"),
            "qrUrl": f"{verify_base}/{quote(ma)}" if verify_base else "",
            "pdfPath": str(pdf_path)}


def handle_gui_thong_bao(variables: dict, headers: dict) -> dict:
    mau = headers.get("mau", "chung")
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    if not smtp_host:
        raise RuntimeError("Chưa cấu hình SMTP_HOST; không thể gửi email thông báo.")

    if mau == "nhac-duyet":
        to_address = os.getenv("STAFF_NOTIFICATION_EMAIL", "").strip()
        if not to_address:
            raise RuntimeError("Chưa cấu hình STAFF_NOTIFICATION_EMAIL để nhận email nhắc duyệt.")
    else:
        to_address = (os.getenv("EMAIL_OVERRIDE_TO", "").strip()
                      or str(variables.get("email", "")).strip())
        if not to_address:
            raise RuntimeError(
                f"Không có email người nhận cho thông báo '{mau}' (MSSV {variables.get('mssv', '')})."
            )

    ho_ten = str(variables.get("hoTen", "Sinh viên"))
    mssv = str(variables.get("mssv", ""))
    muc_dich = str(variables.get("mucDich", ""))
    subjects = {
        "da-cap-ban-dien-tu": "Giấy xác nhận sinh viên đã được cấp",
        "tu-choi": "Yêu cầu cấp giấy xác nhận cần được bổ sung",
        "khong-du-dieu-kien": "Thông báo về yêu cầu cấp giấy xác nhận",
        "nhac-duyet": f"Nhắc duyệt yêu cầu cấp giấy xác nhận của {ho_ten}",
    }

    if mau == "da-cap-ban-dien-tu":
        so_giay = str(variables.get("soGiay", ""))
        ma_xac_thuc = str(variables.get("maXacThuc", ""))
        body = (f"Chào {ho_ten},\n\nGiấy xác nhận sinh viên đã được cấp.\n"
                f"MSSV: {mssv}\nMục đích: {muc_dich}\nSố giấy: {so_giay}\n"
                f"Mã xác thực: {ma_xac_thuc}\n\nFile PDF được đính kèm trong email này.")
    elif mau == "tu-choi":
        ly_do = str(variables.get("lyDoDuyet") or variables.get("ghiChu") or "Vui lòng liên hệ CTSV.")
        body = (f"Chào {ho_ten},\n\nYêu cầu cấp giấy xác nhận của bạn cần được bổ sung.\n"
                f"MSSV: {mssv}\nMục đích: {muc_dich}\nLý do: {ly_do}\n")
    elif mau == "khong-du-dieu-kien":
        trang_thai = str(variables.get("trangThaiHocTap", "Không đủ điều kiện"))
        body = (f"Chào {ho_ten},\n\nYêu cầu cấp giấy xác nhận chưa đủ điều kiện xử lý.\n"
                f"MSSV: {mssv}\nTình trạng tra cứu: {trang_thai}\n")
    elif mau == "nhac-duyet":
        body = (f"Kính gửi cán bộ CTSV,\n\nYêu cầu cấp giấy xác nhận đã chờ duyệt quá thời hạn.\n"
                f"Sinh viên: {ho_ten} ({mssv})\nMục đích: {muc_dich}\n")
    else:
        body = (f"Thông báo về yêu cầu cấp giấy xác nhận của {ho_ten} ({mssv}).\n"
                f"Mục đích: {muc_dich}\n")

    message = EmailMessage()
    message["Subject"] = subjects.get(mau, "Thông báo cấp giấy xác nhận sinh viên")
    message["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")).strip()
    if not message["From"]:
        raise RuntimeError("Cần cấu hình SMTP_FROM hoặc SMTP_USER làm địa chỉ gửi.")
    message["To"] = to_address
    message.set_content(body)

    attachment_path = None
    if mau == "da-cap-ban-dien-tu":
        pdf_value = str(variables.get("pdfPath", "")).strip()
        if not pdf_value:
            raise RuntimeError("Không có pdfPath; từ chối gửi email cấp giấy khi thiếu file PDF.")
        attachment_path = Path(pdf_value)
        if not attachment_path.is_file():
            raise FileNotFoundError(f"Không tìm thấy PDF để đính kèm: {attachment_path}")
        message.add_attachment(attachment_path.read_bytes(), maintype="application", subtype="pdf",
                               filename=attachment_path.name)

    port = int(os.getenv("SMTP_PORT", "587"))
    timeout = float(os.getenv("SMTP_TIMEOUT", "30"))
    use_ssl = os.getenv("SMTP_USE_SSL", "false").strip().lower() in {"1", "true", "yes", "on"}
    use_starttls = os.getenv("SMTP_STARTTLS", "true").strip().lower() in {"1", "true", "yes", "on"}
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(smtp_host, port, timeout=timeout) as smtp:
        if not use_ssl and use_starttls:
            smtp.starttls()
        smtp_user = os.getenv("SMTP_USER", "").strip()
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        if smtp_user:
            if not smtp_password:
                raise RuntimeError("Đã đặt SMTP_USER nhưng thiếu SMTP_PASSWORD.")
            smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)

    print(f"  gui-thong-bao [{mau}]: đã gửi tới {to_address}"
          f" ({'kèm ' + attachment_path.name if attachment_path else 'không đính kèm file'})")
    return {"trangThaiYeuCau": mau, "emailDaGui": True}


HANDLERS = {"tra-cuu-mssv": handle_tra_cuu, "gui-ket-qua": handle_gui_ket_qua,
            "sinh-giay-pdf": handle_sinh_pdf, "gui-thong-bao": handle_gui_thong_bao}


def main() -> None:
    print(f"Worker '{WORKER}' đang chờ job tại {api.BASE_URL} ...")
    while True:
        for job_type, handler in HANDLERS.items():
            try:
                jobs = api.activate_jobs(job_type, WORKER, request_timeout_ms=5_000)
            except Exception as exc:  # engine chưa chạy, mất kết nối...
                print(f"Lỗi kết nối: {exc}. Thử lại sau 5 giây.")
                time.sleep(5)
                continue
            for job in jobs:
                key = job["jobKey"]
                print(f"[{job_type}] job {key} (instance {job['processInstanceKey']})")
                try:
                    vars_ = job.get("variables", {})
                    if job_type == "gui-thong-bao":
                        out = handler(vars_, job.get("customHeaders", {}))
                    else:
                        out = handler(vars_)
                    api.complete_job(key, out)
                except Exception as exc:
                    api.fail_job(key, max(job.get("retries", 1) - 1, 0), str(exc))
                    print(f"  thất bại: {exc}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Đã dừng worker.")
