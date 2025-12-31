import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class LogParser:
    """Log dosyalarını parse eden sınıf"""

    # Log seviyesi pattern'leri
    LOG_LEVEL_PATTERNS = {
        "ERROR": [
            r"\bERROR\b",
            r"\bError\b",
            r"\b[Ee]rror\b",
            r"\bFATAL\b",
            r"\bCRITICAL\b",
            r"\bException\b",
        ],
        "WARNING": [r"\bWARNING\b", r"\bWarning\b", r"\bWARN\b", r"\bWarn\b"],
        "INFO": [r"\bINFO\b", r"\bInfo\b", r"\bINFORMATION\b"],
        "DEBUG": [r"\bDEBUG\b", r"\bDebug\b"],
    }

    # Tarih format pattern'leri
    TIMESTAMP_PATTERNS = [
        r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}",  # 2024-01-15 10:30:45
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}",  # 2024-01-15T10:30:45
        r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}",  # 15/01/2024 10:30:45
        r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]",  # [2024-01-15 10:30:45]
    ]

    def __init__(self):
        self.compiled_level_patterns = {}
        for level, patterns in self.LOG_LEVEL_PATTERNS.items():
            self.compiled_level_patterns[level] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]

    def detect_log_level(self, line: str) -> Optional[str]:
        """Satırdan log seviyesini tespit et"""
        for level in ["ERROR", "WARNING", "INFO", "DEBUG"]:
            for pattern in self.compiled_level_patterns[level]:
                if pattern.search(line):
                    return level
        return None

    def extract_timestamp(self, line: str) -> Optional[datetime]:
        """Satırdan timestamp'i çıkar"""
        for pattern_str in self.TIMESTAMP_PATTERNS:
            pattern = re.compile(pattern_str)
            match = pattern.search(line)
            if match:
                timestamp_str = match.group().strip("[]")
                try:
                    # Farklı formatları dene
                    for fmt in [
                        "%Y-%m-%d %H:%M:%S",
                        "%Y-%m-%dT%H:%M:%S",
                        "%d/%m/%Y %H:%M:%S",
                    ]:
                        try:
                            return datetime.strptime(timestamp_str, fmt)
                        except ValueError:
                            continue
                except Exception as e:
                    logger.debug(f"Timestamp parse hatası: {e}")
                    return None
        return None

    def parse_line(self, line: str, line_number: int) -> Dict:
        """Bir log satırını parse et"""
        line = line.strip()
        if not line:
            return None

        log_level = self.detect_log_level(line)
        timestamp = self.extract_timestamp(line)

        # Mesajı temizle
        message = line
        if timestamp:
            # Timestamp'i mesajdan çıkar
            for pattern_str in self.TIMESTAMP_PATTERNS:
                message = re.sub(pattern_str, "", message).strip()

        # Log level'ı mesajdan çıkar
        if log_level:
            for pattern in self.compiled_level_patterns[log_level]:
                message = pattern.sub("", message).strip()

        # Fazla boşlukları temizle
        message = " ".join(message.split())

        return {
            "line_number": line_number,
            "log_level": log_level,
            "timestamp": timestamp,
            "message": message if message else line,
            "raw_line": line,
        }

    def parse_file(self, file_content: str) -> List[Dict]:
        """Tüm log dosyasını parse et"""
        lines = file_content.split("\n")
        parsed_lines = []

        for idx, line in enumerate(lines, start=1):
            parsed = self.parse_line(line, idx)
            if parsed:
                parsed_lines.append(parsed)

        return parsed_lines
