# logger.py
import logging
from datetime import datetime

def setup_logger(tags, name=__name__):
    now = datetime.now().strftime('%Y%m%d_%H%M')
    log_file=f'./app/logs/insta_crawler_{tags}_{now}.log'
    formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')

    # 파일 핸들러
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # 콘솔 핸들러
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger
