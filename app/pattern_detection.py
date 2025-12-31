"""
Log Pattern Detection - Otomatik pattern tespiti ve benzer hataları gruplama
"""

from typing import List, Dict, Any
from collections import Counter
import re
from difflib import SequenceMatcher


def detect_patterns(
    log_entries: List[Dict[str, Any]], min_similarity: float = 0.7
) -> Dict[str, Any]:
    """
    Log girişlerinden pattern'leri tespit et ve benzer hataları grupla

    Args:
        log_entries: Log entry listesi (dict formatında)
        min_similarity: Minimum benzerlik oranı (0-1 arası)

    Returns:
        Pattern detection sonuçları
    """
    if not log_entries:
        return {"patterns": [], "groups": [], "total_patterns": 0, "total_groups": 0}

    # Sadece ERROR ve WARNING seviyelerindeki logları analiz et
    error_warning_logs = [
        entry for entry in log_entries if entry.get("log_level") in ["ERROR", "WARNING"]
    ]

    if not error_warning_logs:
        return {"patterns": [], "groups": [], "total_patterns": 0, "total_groups": 0}

    # Pattern'leri tespit et
    patterns = extract_patterns(error_warning_logs)

    # Benzer hataları grupla
    groups = group_similar_errors(error_warning_logs, min_similarity)

    return {
        "patterns": patterns,
        "groups": groups,
        "total_patterns": len(patterns),
        "total_groups": len(groups),
        "analyzed_logs": len(error_warning_logs),
    }


def extract_patterns(log_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Log mesajlarından ortak pattern'leri çıkar

    Pattern türleri:
    - URL pattern'leri
    - IP adresleri
    - Tarih/saat formatları
    - Hata kodları
    - SQL hataları
    - API endpoint'leri
    """
    patterns = []
    messages = [entry.get("message", "") for entry in log_entries]

    # URL pattern'leri
    url_pattern = re.compile(r"https?://[^\s]+")
    urls = []
    for msg in messages:
        urls.extend(url_pattern.findall(msg))
    if urls:
        patterns.append(
            {
                "type": "url",
                "pattern": "URL pattern",
                "count": len(urls),
                "examples": list(set(urls))[:5],
            }
        )

    # IP adresleri
    ip_pattern = re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b")
    ips = []
    for msg in messages:
        ips.extend(ip_pattern.findall(msg))
    if ips:
        patterns.append(
            {
                "type": "ip",
                "pattern": "IP address pattern",
                "count": len(ips),
                "examples": list(set(ips))[:5],
            }
        )

    # HTTP status kodları
    status_pattern = re.compile(r"\b(?:HTTP/\d\.\d\s+)?(\d{3})\b")
    status_codes = []
    for msg in messages:
        matches = status_pattern.findall(msg)
        status_codes.extend([int(s) for s in matches if s.isdigit()])
    if status_codes:
        status_counter = Counter(status_codes)
        patterns.append(
            {
                "type": "http_status",
                "pattern": "HTTP status codes",
                "count": len(status_codes),
                "examples": [
                    {"code": code, "count": count}
                    for code, count in status_counter.most_common(5)
                ],
            }
        )

    # SQL hataları
    sql_keywords = ["SELECT", "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER"]
    sql_errors = []
    for msg in messages:
        if any(keyword in msg.upper() for keyword in sql_keywords):
            sql_errors.append(msg[:100])
    if sql_errors:
        patterns.append(
            {
                "type": "sql",
                "pattern": "SQL-related errors",
                "count": len(sql_errors),
                "examples": list(set(sql_errors))[:5],
            }
        )

    # API endpoint'leri
    endpoint_pattern = re.compile(r"(?:GET|POST|PUT|DELETE|PATCH)\s+([/\w\-]+)")
    endpoints = []
    for msg in messages:
        endpoints.extend(endpoint_pattern.findall(msg))
    if endpoints:
        endpoint_counter = Counter(endpoints)
        patterns.append(
            {
                "type": "api_endpoint",
                "pattern": "API endpoints",
                "count": len(endpoints),
                "examples": [
                    {"endpoint": ep, "count": count}
                    for ep, count in endpoint_counter.most_common(5)
                ],
            }
        )

    # Exception türleri
    exception_pattern = re.compile(r"(\w+Exception|\w+Error|\w+Warning)")
    exceptions = []
    for msg in messages:
        exceptions.extend(exception_pattern.findall(msg))
    if exceptions:
        exception_counter = Counter(exceptions)
        patterns.append(
            {
                "type": "exception",
                "pattern": "Exception types",
                "count": len(exceptions),
                "examples": [
                    {"type": exc, "count": count}
                    for exc, count in exception_counter.most_common(5)
                ],
            }
        )

    return patterns


def group_similar_errors(
    log_entries: List[Dict[str, Any]], min_similarity: float = 0.7
) -> List[Dict[str, Any]]:
    """
    Benzer hataları grupla (mesaj benzerliğine göre)

    Args:
        log_entries: Log entry listesi
        min_similarity: Minimum benzerlik oranı

    Returns:
        Gruplanmış hatalar
    """
    if not log_entries:
        return []

    groups = []
    processed = set()

    for i, entry1 in enumerate(log_entries):
        if i in processed:
            continue

        message1 = entry1.get("message", "").lower()
        if not message1:
            continue

        # Yeni grup oluştur
        group = {
            "id": len(groups) + 1,
            "representative": entry1.get("message", "")[:100],
            "count": 1,
            "log_level": entry1.get("log_level", "UNKNOWN"),
            "entries": [entry1],
            "similarity_score": 1.0,
        }

        # Benzer hataları bul
        for j, entry2 in enumerate(log_entries[i + 1 :], start=i + 1):
            if j in processed:
                continue

            message2 = entry2.get("message", "").lower()
            if not message2:
                continue

            similarity = calculate_similarity(message1, message2)

            if similarity >= min_similarity:
                group["count"] += 1
                group["entries"].append(entry2)
                processed.add(j)

        if group["count"] > 1:  # Sadece 2+ benzer hata içeren grupları ekle
            groups.append(group)
            processed.add(i)

    # Grupları sayıya göre sırala
    groups.sort(key=lambda x: x["count"], reverse=True)

    return groups[:20]  # En fazla 20 grup döndür


def calculate_similarity(str1: str, str2: str) -> float:
    """
    İki string arasındaki benzerliği hesapla

    SequenceMatcher kullanarak benzerlik oranını hesaplar
    """
    if not str1 or not str2:
        return 0.0

    # Basit kelime bazlı benzerlik
    words1 = set(str1.split())
    words2 = set(str2.split())

    if not words1 or not words2:
        return 0.0

    # Jaccard similarity
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    jaccard = intersection / union if union > 0 else 0.0

    # SequenceMatcher benzerliği
    sequence_similarity = SequenceMatcher(None, str1, str2).ratio()

    # Ortalama al
    return jaccard * 0.4 + sequence_similarity * 0.6


def normalize_message(message: str) -> str:
    """
    Log mesajını normalize et (pattern tespiti için)

    - IP adreslerini <IP> ile değiştir
    - Tarihleri <DATE> ile değiştir
    - Sayıları <NUMBER> ile değiştir
    """
    if not message:
        return ""

    normalized = message

    # IP adresleri
    normalized = re.sub(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "<IP>", normalized)

    # Tarihler
    normalized = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "<DATE>", normalized)
    normalized = re.sub(r"\b\d{2}/\d{2}/\d{4}\b", "<DATE>", normalized)

    # Sayılar (büyük sayılar)
    normalized = re.sub(r"\b\d{4,}\b", "<NUMBER>", normalized)

    return normalized
