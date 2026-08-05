"""扫描型 PDF / 图片 OCR 工具（RapidOCR，ONNX Runtime，无需 Paddle）。

用法示例：
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    result, elapse = engine("扫描件.png")
    for box, text, score in result:
        print(text)

应用内的扫描型 PDF 识别已集成在 src/parser.py：
上传时自动检测图片型 PDF → 前端提示用户 → 确认后逐页 OCR 入库。
"""

from rapidocr_onnxruntime import RapidOCR


ocr = RapidOCR()
