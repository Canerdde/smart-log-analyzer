from typing import Dict, Any, Optional
import os

# OpenAI API'si isteğe bağlı - env'de API key yoksa devre dışı kalır
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class AIService:
    """AI tabanlı log analizi ve yorumlama servisi"""

    def __init__(self):
        self.openai_client = None
        if OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                try:
                    self.openai_client = OpenAI(api_key=api_key)
                except Exception as e:
                    print(f"OpenAI client başlatma hatası: {e}")
                    self.openai_client = None

    def analyze_logs(
        self, analysis_data: Dict[str, Any], log_sample: list = None
    ) -> Dict[str, Any]:
        """Log analizini AI ile zenginleştir"""
        if not self.openai_client:
            return {"ai_comment": None, "ai_suggestions": None}

        try:
            # Analiz verilerinden özet çıkar
            summary = self._create_summary(analysis_data, log_sample)

            # OpenAI'a prompt gönder
            prompt = f"""Bir log analiz raporu inceleyip yorum yap. Analiz sonuçları:

{summary}

Lütfen şunları sağla:
1. Kısa bir genel değerlendirme (2-3 cümle)
2. Potansiyel sorunlar ve çözüm önerileri
3. Dikkat edilmesi gereken noktalar

Yanıtı Türkçe olarak, JSON formatında döndür:
{{
    "comment": "genel yorum",
    "suggestions": {{
        "critical_issues": ["sorun1", "sorun2"],
        "recommendations": ["öneri1", "öneri2"]
    }}
}}
"""

            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Sen bir log analiz uzmanısın. Log dosyalarını analiz edip yorum yapıyorsun.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )

            content = response.choices[0].message.content

            # JSON parse et
            import json

            try:
                ai_response = json.loads(content)
                return {
                    "ai_comment": ai_response.get("comment", ""),
                    "ai_suggestions": ai_response.get("suggestions", {}),
                }
            except:
                return {"ai_comment": content, "ai_suggestions": {}}

        except Exception as e:
            print(f"AI analiz hatası: {e}")
            return {"ai_comment": None, "ai_suggestions": None}

    def _create_summary(
        self, analysis_data: Dict[str, Any], log_sample: list = None
    ) -> str:
        """Analiz verilerinden özet metin oluştur"""
        summary_lines = [
            f"Toplam Log Girişi: {analysis_data.get('total_entries', 0)}",
            f"Hata Sayısı: {analysis_data.get('error_count', 0)}",
            f"Uyarı Sayısı: {analysis_data.get('warning_count', 0)}",
            f"Bilgi Sayısı: {analysis_data.get('info_count', 0)}",
        ]

        top_errors = analysis_data.get("top_errors", [])
        if top_errors:
            summary_lines.append("\nEn Sık Tekrar Eden Hatalar:")
            for i, error in enumerate(top_errors[:5], 1):
                summary_lines.append(
                    f"  {i}. {error.get('message', '')[:100]} ({error.get('count', 0)} kez)"
                )

        if log_sample:
            summary_lines.append("\nLog Örnekleri:")
            for entry in log_sample[:5]:
                level = entry.get("log_level", "UNKNOWN")
                msg = entry.get("message", "")[:100]
                summary_lines.append(f"  [{level}] {msg}")

        return "\n".join(summary_lines)
