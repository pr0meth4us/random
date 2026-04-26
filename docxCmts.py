import zipfile
import xml.etree.ElementTree as ET
import json
from docx import Document


def extract_docx_data(docx_path):
    data = {}

    # ---- Extract document text ----
    doc = Document(docx_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip() != ""]
    data["content"] = paragraphs

    # ---- Extract comments ----
    comments = []

    with zipfile.ZipFile(docx_path, "r") as z:
        if "word/comments.xml" in z.namelist():
            xml = z.read("word/comments.xml")
            root = ET.fromstring(xml)

            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

            for c in root.findall(".//w:comment", ns):
                author = c.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}author")
                date = c.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}date")

                text = ""
                for t in c.findall(".//w:t", ns):
                    if t.text:
                        text += t.text

                comments.append({
                    "author": author,
                    "date": date,
                    "text": text
                })

    data["comments"] = comments
    return data


# ---- Run ----
input_file = "Draft_Digital_Diagnostic_Tools_Design_Tourism_08022026_v_02.docx"
output_file = "output.json"

data = extract_docx_data(input_file)

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print(f"Saved document text + comments to {output_file}")