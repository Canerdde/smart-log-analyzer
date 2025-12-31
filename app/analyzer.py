from typing import List, Dict, Any
from collections import Counter, defaultdict
from datetime import datetime
import json


class LogAnalyzer:
    """Log verilerini analiz eden sınıf"""

    def __init__(self):
        pass

    def analyze(self, log_entries: List[Dict]) -> Dict[str, Any]:
        """Log girişlerini analiz et ve istatistikler üret"""
        if not log_entries:
            return self._empty_analysis()

        # Temel istatistikler
        total_entries = len(log_entries)
        level_counts = Counter(entry.get("log_level") for entry in log_entries)
        error_count = level_counts.get("ERROR", 0)
        warning_count = level_counts.get("WARNING", 0)
        info_count = level_counts.get("INFO", 0)
        debug_count = level_counts.get("DEBUG", 0)

        # En sık tekrar eden hatalar
        error_messages = [
            entry.get("message", "")
            for entry in log_entries
            if entry.get("log_level") == "ERROR"
        ]
        top_errors = self._get_top_messages(error_messages, limit=10)

        # En sık tekrar eden uyarılar
        warning_messages = [
            entry.get("message", "")
            for entry in log_entries
            if entry.get("log_level") == "WARNING"
        ]
        top_warnings = self._get_top_messages(warning_messages, limit=10)

        # Zaman dağılımı
        time_distribution = self._get_time_distribution(log_entries)

        return {
            "total_entries": total_entries,
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
            "debug_count": debug_count,
            "top_errors": top_errors,
            "top_warnings": top_warnings,
            "time_distribution": time_distribution,
        }

    def _get_top_messages(
        self, messages: List[str], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """En sık tekrar eden mesajları bul"""
        if not messages:
            return []

        # Mesajları normalize et (büyük/küçük harf farkını göz ardı et)
        normalized = [msg.lower().strip() for msg in messages if msg.strip()]

        counter = Counter(normalized)
        top_items = counter.most_common(limit)

        return [
            {
                "message": message,
                "count": count,
                "percentage": (
                    round((count / len(messages)) * 100, 2) if messages else 0
                ),
            }
            for message, count in top_items
        ]

    def _get_time_distribution(self, log_entries: List[Dict]) -> Dict[str, int]:
        """Log girişlerinin saatlere göre dağılımını hesapla"""
        hour_counts = defaultdict(int)

        for entry in log_entries:
            timestamp = entry.get("timestamp")
            if timestamp:
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                    except:
                        continue
                elif isinstance(timestamp, datetime):
                    pass
                else:
                    continue

                hour = timestamp.hour
                hour_counts[str(hour)] = hour_counts.get(str(hour), 0) + 1

        return dict(hour_counts)

    def _empty_analysis(self) -> Dict[str, Any]:
        """Boş analiz sonucu döndür"""
        return {
            "total_entries": 0,
            "error_count": 0,
            "warning_count": 0,
            "info_count": 0,
            "debug_count": 0,
            "top_errors": [],
            "top_warnings": [],
            "time_distribution": {},
        }
