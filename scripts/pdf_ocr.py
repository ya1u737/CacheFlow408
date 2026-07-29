from paddleocr import PaddleOCR


ocr = PaddleOCR(
    lang="ch",
    det_model_dir=r"D:\408-RAG-bot\models\paddleocr\det",
    rec_model_dir=r"D:\408-RAG-bot\models\paddleocr\rec",
    cls_model_dir=r"D:\408-RAG-bot\models\paddleocr\cls",
    use_angle_cls=True
)