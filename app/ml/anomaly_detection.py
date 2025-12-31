"""
AI/ML Anomali Tespiti
Log girişlerinde anormal pattern'leri tespit eder
"""

import warnings
from datetime import datetime
from typing import Any, Dict, List

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")


class AnomalyDetector:
    """Log girişlerinde anomali tespit eden sınıf"""

    def __init__(self, contamination=0.1):
        """
        Args:
            contamination: Anomali oranı tahmini (0.1 = %10)
        """
        self.contamination = contamination
        self.model = IsolationForest(
            contamination=contamination, random_state=42, n_estimators=100
        )
        self.scaler = StandardScaler()

    def extract_features(self, log_entries: List[Dict]) -> np.ndarray:
        """
        Log girişlerinden özellik çıkarımı yap

        Features:
        - Timestamp hour (0-23)
        - Day of week (0-6)
        - Log level (encoded: ERROR=3, WARNING=2, INFO=1, DEBUG=0)
        - Message length
        - Has error keywords (boolean)
        """
        features = []

        error_keywords = [
            "error",
            "exception",
            "failed",
            "timeout",
            "deadlock",
            "crash",
        ]

        for entry in log_entries:
            timestamp = entry.get("timestamp")

            # Timestamp özellikleri
            if timestamp:
                if isinstance(timestamp, str):
                    try:
                        timestamp = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )
                    except:
                        timestamp = None

                if isinstance(timestamp, datetime):
                    hour = timestamp.hour
                    day_of_week = timestamp.weekday()
                else:
                    hour = 12  # Varsayılan
                    day_of_week = 0
            else:
                hour = 12
                day_of_week = 0

            # Log seviyesi encoding
            log_level = entry.get("log_level", "INFO")
            level_encoded = {"ERROR": 3, "WARNING": 2, "INFO": 1, "DEBUG": 0}.get(
                log_level, 1
            )

            # Mesaj uzunluğu
            message = entry.get("message", "")
            message_length = len(message)

            # Hata keyword kontrolü
            message_lower = message.lower()
            has_error_keywords = any(
                keyword in message_lower for keyword in error_keywords
            )

            features.append(
                [
                    hour,
                    day_of_week,
                    level_encoded,
                    message_length,
                    1 if has_error_keywords else 0,
                ]
            )

        return np.array(features)

    def detect_anomalies(self, log_entries: List[Dict]) -> List[Dict[str, Any]]:
        """
        Log girişlerinde anomali tespit et

        Returns:
            Anomali olarak tespit edilen girişlerin listesi
        """
        if len(log_entries) < 10:
            # Çok az veri varsa anomali tespiti yapma
            return []

        # Özellik çıkarımı
        features = self.extract_features(log_entries)

        # Normalize et
        features_scaled = self.scaler.fit_transform(features)

        # Anomali tespiti
        predictions = self.model.fit_predict(features_scaled)

        # Anomali olarak işaretlenenleri bul (-1 = anomali, 1 = normal)
        anomalies = []
        for idx, (entry, prediction) in enumerate(zip(log_entries, predictions)):
            if prediction == -1:
                # Anomali skoru hesapla (decision function'dan)
                anomaly_score = self.model.score_samples([features_scaled[idx]])[0]
                anomalies.append(
                    {
                        "entry": entry,
                        "anomaly_score": float(anomaly_score),
                        "index": idx,
                    }
                )

        # Anomali skoruna göre sırala (en anormal olanlar önce)
        anomalies.sort(key=lambda x: x["anomaly_score"])

        return anomalies

    def get_anomaly_summary(self, log_entries: List[Dict]) -> Dict[str, Any]:
        """
        Anomali tespiti özeti döndür

        Returns:
            Anomali istatistikleri ve örnekler
        """
        anomalies = self.detect_anomalies(log_entries)

        if not anomalies:
            return {
                "has_anomalies": False,
                "anomaly_count": 0,
                "anomaly_percentage": 0.0,
                "anomalies": [],
            }

        anomaly_count = len(anomalies)
        total_count = len(log_entries)

        # En anormal 10 örnek
        top_anomalies = [
            {
                "line_number": anom["entry"].get("line_number"),
                "log_level": anom["entry"].get("log_level"),
                "message": anom["entry"].get("message", "")[:200],
                "timestamp": anom["entry"].get("timestamp"),
                "anomaly_score": anom["anomaly_score"],
            }
            for anom in anomalies[:10]
        ]

        return {
            "has_anomalies": True,
            "anomaly_count": anomaly_count,
            "anomaly_percentage": round((anomaly_count / total_count) * 100, 2),
            "total_entries": total_count,
            "top_anomalies": top_anomalies,
            "recommendation": self._get_recommendation(anomaly_count, total_count),
        }

    def _get_recommendation(self, anomaly_count: int, total_count: int) -> str:
        """Anomali sayısına göre öneri oluştur"""
        percentage = (anomaly_count / total_count) * 100

        if percentage > 20:
            return "Yüksek anomali oranı tespit edildi. Sistem genelinde bir sorun olabilir."
        elif percentage > 10:
            return "Orta seviye anomali oranı. Bu logların incelenmesi önerilir."
        elif percentage > 5:
            return "Düşük seviye anomali oranı. Normal sınırlar içinde."
        else:
            return "Anomali oranı çok düşük. Sistem normal çalışıyor gibi görünüyor."
