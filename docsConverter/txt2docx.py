from docx import Document

def txt_to_docx(txt_path, docx_path):
    document = Document()

    with open(txt_path, 'r', encoding='utf-8') as file:
        for line in file:
            document.add_paragraph(line.strip())

    document.save(docx_path)
    print("Conversion complete.")

# Example usage
txt_to_docx("index (2).txt", "output.docx")
