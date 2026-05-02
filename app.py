import os
import io
import base64
import urllib.request
import fitz  # PyMuPDF
from flask import Flask, request, jsonify, send_file

app = Flask(__name__)

TEMPLATE_URL = "https://files.manuscdn.com/user_upload_by_module/session_file/112574404/CRldWkvlXFkamsKs.pdf"
BG_COLOR = (0.914, 0.882, 0.820)

# Cache the template in memory after first download
_template_bytes = None

def get_template():
    global _template_bytes
    if _template_bytes is None:
        with urllib.request.urlopen(TEMPLATE_URL) as resp:
            _template_bytes = resp.read()
    return _template_bytes

def fill_pdf(first_name, edition_number):
    edition_str = str(int(edition_number)).zfill(3)
    replacements = {
        "SORDOE_NAME": first_name,
        "SORDOE_NUM": edition_str,
    }

    pdf_bytes = get_template()
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page in doc:
        spans_to_replace = []
        for block in page.get_text("dict")["blocks"]:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    for placeholder, value in replacements.items():
                        if placeholder in span["text"]:
                            spans_to_replace.append({
                                "bbox": fitz.Rect(span["bbox"]),
                                "text": span["text"].replace(placeholder, value),
                                "font": span["font"],
                                "size": span["size"],
                                "color": span["color"],
                            })

        for s in spans_to_replace:
            page.add_redact_annot(s["bbox"], fill=BG_COLOR)
        page.apply_redactions()

        for s in spans_to_replace:
            fn = s["font"]
            if "Grotesk" in fn or "HK" in fn:
                font_name = ("Helvetica-Oblique" if ("Italic" in fn or "italic" in fn)
                             else "Helvetica-Bold" if "Bold" in fn else "Helvetica")
            else:
                font_name = ("Times-Italic" if ("Italic" in fn or "italic" in fn)
                             else "Times-Bold" if "Bold" in fn else "Times-Roman")

            c = s["color"]
            r = ((c >> 16) & 0xFF) / 255.0
            g = ((c >> 8) & 0xFF) / 255.0
            b = (c & 0xFF) / 255.0

            page.insert_text(
                (s["bbox"].x0, s["bbox"].y1 - 1),
                s["text"],
                fontname=font_name,
                fontsize=s["size"],
                color=(r, g, b)
            )

    out_buf = io.BytesIO()
    doc.save(out_buf, garbage=4, deflate=True)
    doc.close()
    out_buf.seek(0)
    return out_buf, edition_str


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    first_name = data.get("first_name", "Friend")
    edition_number = data.get("edition_number", 1)

    try:
        pdf_buf, edition_str = fill_pdf(first_name, int(float(str(edition_number).strip())))
        filename = f"Sordoe_Opening_{first_name}_{edition_str}.pdf"
        pdf_b64 = base64.b64encode(pdf_buf.read()).decode("utf-8")
        return jsonify({
            "success": True,
            "filename": filename,
            "pdf_base64": pdf_b64,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
