import fitz
import os
from docx import Document as DocxDocument
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from src.config import Config


class DocumentParser:
    def __init__(self):
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP,
            separators=["\n\n", "\n", "。", " "]
        )
    # ===== 统一入口：根据文件后缀自动分流 =====
    def parse(self, file):
        if isinstance(file, str):
            ext = os.path.splitext(file)[1].lower()
        else:
            ext = os.path.splitext(file.name)[1].lower()

        if ext == ".pdf":
            return self.parse_pdf(file)
        elif ext in (".txt", ".md"):
            return self.parse_txt(file)
        elif ext == ".docx":
            return self.parse_docx(file)
        else:
            raise ValueError(f"不支持的文件类型: {ext}")

    # ===== PDF解析（支持路径 + 上传）=====
    def parse_pdf(self, file):
        if isinstance(file, str):
            doc = fitz.open(file)
            file_name = os.path.basename(file)
        else:
            doc = fitz.open(stream=file.read(), filetype="pdf")
            file_name = file.name

        documents = []

        for page_num, page in enumerate(doc):
            text = page.get_text().strip()
            if text:
                documents.append(
                    Document(
                        page_content=text,
                        metadata={
                            "source": file_name,
                            "page": page_num + 1,
                            "type": "pdf"
                        }
                    )
                )

        return self.splitter.split_documents(documents)

    # ===== TXT/Markdown 解析（支持路径字符串 + 上传文件对象） =====
    def parse_txt(self, file):
        if isinstance(file, str):
            with open(file, "r", encoding="utf-8") as f:
                text = f.read()
            file_name = os.path.basename(file)
        else:
            text = file.read().decode("utf-8")
            file_name = file.name

        return self.splitter.create_documents(
            [text],
            metadatas=[{"source": file_name, "page": 1, "type": "md"}]
        )

    # ===== DOCX 解析（段落 + 表格） =====
    def parse_docx(self, file):
        docx = DocxDocument(file)
        file_name = file.name

        parts = []

        # 1. 提取所有段落文本
        paragraph_texts = []
        for para in docx.paragraphs:
            text = para.text.strip()
            if text:
                paragraph_texts.append(text)

        if paragraph_texts:
            parts.append("\n".join(paragraph_texts))

        # 2. 提取所有表格内容
        for table in docx.tables:
            table_lines = []
            if table.rows:
                header_cells = [cell.text.strip() for cell in table.rows[0].cells]
                for row in table.rows[1:]:
                    cell_texts = [cell.text.strip() for cell in row.cells]
                    if len(header_cells) == len(cell_texts):
                        row_text = " | ".join(
                            f"{h}: {v}" for h, v in zip(header_cells, cell_texts) if v
                        )
                    else:
                        row_text = " | ".join(filter(None, cell_texts))
                    if row_text.strip():
                        table_lines.append(row_text)

            if table_lines:
                parts.append("\n".join(table_lines))

        if not parts:
            return []

        combined_text = "\n\n".join(parts)

        return self.splitter.create_documents(
            [combined_text],
            metadatas=[{"source": file_name, "page": "N/A", "type": "docx"}]
        )
