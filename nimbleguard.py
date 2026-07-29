"""NimbleGuard - أداة خفيفة للفحص المحلي والعناية الآمنة بويندوز.

هذا البرنامج لا يدّعي استبدال Microsoft Defender أو أي مضاد فيروسات احترافي.
بدلاً من الحذف التلقائي، يقيّم الملفات بمؤشرات قابلة للشرح ويترك القرار للمستخدم.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import os
import queue
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

try:
    import winreg
except ImportError:  # يبقى المشروع قابلاً للفحص خارج Windows، دون ميزة بدء التشغيل.
    winreg = None

try:
    import customtkinter as ctk
    import psutil
    from tkinter import filedialog, messagebox
except ImportError as error:
    raise SystemExit(
        "المكتبات المطلوبة غير مثبتة. شغّل: pip install -r requirements.txt\n"
        f"التفاصيل: {error}"
    ) from error


# لا نغيّر السجل أو نوقف العمليات أو نحذف الملفات أثناء الفحص؛ هذه حدود أمان مقصودة.
APP_NAME = "NimbleGuard"
APP_VERSION = "0.6"
APP_DIR = Path(os.getenv("LOCALAPPDATA", Path.home())) / APP_NAME
QUARANTINE_DIR = APP_DIR / "quarantine"
HISTORY_FILE = APP_DIR / "history.json"
STARTUP_BACKUP_FILE = APP_DIR / "startup_disabled.json"
MAX_FILES_PER_SCAN = 4_000
MAX_HASH_SIZE = 250 * 1024 * 1024  # منع قراءة ملفات ضخمة بالكامل وإجهاد القرص.
SAMPLE_SIZE = 1 * 1024 * 1024

RISKY_EXTENSIONS = {
    ".exe", ".dll", ".scr", ".com", ".msi", ".bat", ".cmd", ".ps1",
    ".vbs", ".vbe", ".js", ".jse", ".wsf", ".hta", ".jar", ".lnk",
}
EXECUTABLE_EXTENSIONS = {".exe", ".dll", ".scr", ".com", ".msi", ".jar"}
CRACK_WORDS = ("crack", "keygen", "patch", "activator", "loader", "serial", "unlock")
MALWARE_WORDS = (
    "ransom", "stealer", "rat", "miner", "cryptominer", "trojan", "backdoor",
    "botnet", "credential", "walletgrab", "clipper",
)
SCRIPT_MARKERS = (
    b"powershell -enc", b"frombase64string", b"downloadstring", b"invoke-webrequest",
    b"wscript.shell", b"mshta", b"curl http", b"bitsadmin", b"start-bitstransfer",
)

# النصوص الرئيسية للواجهة. تبقى تفاصيل التحذير بالعربية لأنها رسائل أمان دقيقة.
TRANSLATIONS = {
    "ar": {
        "language": "العربية", "tagline": "حماية ذكية • خفيفة", "dashboard": "لوحة الحماية",
        "scan": "الفحص الذكي", "quarantine": "الملفات المعزولة", "startup": "بدء التشغيل",
        "boost": "تسريع آمن", "history": "السجل", "on_demand": "الفحص عند الطلب",
        "shield_on": "حماية التنزيلات: مفعلة", "shield_off": "حماية التنزيلات: متوقفة",
        "dashboard_subtitle": "حالة الجهاز وأدوات واضحة — من دون مساحة فارغة أو فحص ثقيل دائم.",
        "cpu": "المعالج", "memory": "الذاكرة RAM", "gpu": "كرت الشاشة GPU", "disk": "المساحة المتاحة",
        "updated": "تحديث خفيف كل 5 ثوانٍ", "hardware": "معلومة العتاد", "system_disk": "قرص النظام",
        "download_shield": "حماية التنزيلات", "download_shield_info": "تفحص فقط الملفات التنفيذية الجديدة في Downloads كل 30 ثانية.",
        "switch_on": "تشغيل الحماية", "switch_off": "الحماية متوقفة", "start_scan": "ابدأ فحصاً ذكياً",
        "safe_clean": "تنظيف آمن", "quick_tools": "أدوات سريعة", "top_apps": "التطبيقات الأكثر استهلاكاً للذاكرة", "top_apps_info": "عرض فقط — لا يتم إغلاق أي تطبيق تلقائياً.",
        "scan_subtitle": "تحليل محلي قابل للتفسير؛ ملفات الكراك لا تعامل كفيروسات تلقائياً.", "scan_choose": "اختر ملفاً أو مجلداً لبدء الفحص", "scan_file": "فحص ملف", "scan_folder": "اختيار مجلد وفحصه", "quick_scan": "فحص سريع للتنزيلات", "stop_scan": "إيقاف الفحص", "export": "تصدير تقرير HTML",
        "quarantine_subtitle": "العزل قابل للاسترجاع؛ الحذف النهائي يحتاج تأكيدين.", "startup_subtitle": "تعطيل قابل للاسترجاع لبرامج حسابك فقط.", "boost_subtitle": "تنظيف الملفات المؤقتة القديمة فقط؛ لا تغيير لملفاتك المهمة.", "history_subtitle": "آخر عمليات NimbleGuard المحلية، من دون إرسال بيانات للإنترنت.",
        "refresh": "تحديث القائمة", "quarantine_hint": "استعد فقط الملفات التي تعرف مصدرها وتثق به.", "quarantine_empty": "لا توجد ملفات معزولة حالياً.", "restore": "استعادة", "permanent_delete": "حذف نهائي", "original_location": "المكان الأصلي",
        "startup_hint": "عطّل فقط برنامجاً تعرف أنه غير ضروري عند بدء Windows.", "startup_empty": "لا توجد برامج بدء تشغيل ظاهرة لحسابك.", "startup_disable": "تعطيل قابل للاسترجاع", "disabled_before": "برامج عطّلتها أنت سابقاً", "registry": "سجل المستخدم", "startup_folder": "مجلد بدء التشغيل",
        "boost_what": "ما الذي سيحدث؟", "boost_description": "• حذف ملفات مؤقتة عمرها 12 ساعة أو أكثر من مجلد المستخدم المؤقت.\n• تجاهل الملفات المقفلة والروابط والمجلدات؛ لا حذف بالقوة.\n• حد أقصى 1,500 ملف و20 ثانية لتبقى العملية خفيفة.", "boost_now": "ϟ خفّف الجهاز الآن", "boost_idle": "العملية لا تعمل في الخلفية.", "history_empty": "لا يوجد سجل بعد.", "scan_results": "نتائج آخر فحص", "scan_ready": "جاهز للفحص عند الطلب",
        "protection_start": "تشغيل الحماية", "protection_stop": "إيقاف الحماية", "defender": "حماية Microsoft Defender", "defender_loading": "جارٍ التحقق من حالة Microsoft Defender…", "defender_quick": "فحص سريع للنظام", "defender_full": "فحص كامل للنظام", "defender_update": "تحديث قاعدة الفيروسات", "defender_note": "يستخدم محرك Microsoft Defender وتواقيعه الحقيقية في Windows.",
        "sidebar_note": "الحماية التلقائية تراقب التنزيلات فقط عند تشغيلها.\nلا حذف تلقائي ولا فحص ثقيل مستمر.",
    },
    "en": {
        "language": "English", "tagline": "Smart • Lightweight protection", "dashboard": "Protection dashboard",
        "scan": "Smart scan", "quarantine": "Quarantine", "startup": "Startup apps", "boost": "Safe cleanup", "history": "History",
        "on_demand": "On-demand scanning", "shield_on": "Downloads shield: on", "shield_off": "Downloads shield: off",
        "dashboard_subtitle": "Clear device status and tools — no empty space or heavy continuous scan.",
        "cpu": "CPU", "memory": "RAM", "gpu": "GPU", "disk": "Free storage",
        "updated": "Light refresh every 5 seconds", "hardware": "Hardware information", "system_disk": "System drive",
        "download_shield": "Downloads shield", "download_shield_info": "Checks only new executable files in Downloads every 30 seconds.",
        "switch_on": "Protection on", "switch_off": "Protection off", "start_scan": "Start smart scan",
        "safe_clean": "Safe cleanup", "quick_tools": "Quick tools", "top_apps": "Highest memory usage", "top_apps_info": "Display only — no app is closed automatically.",
        "scan_subtitle": "Explainable local analysis; cracked files are not automatically treated as malware.", "scan_choose": "Choose a file or folder to begin", "scan_file": "Scan file", "scan_folder": "Choose folder", "quick_scan": "Quick Downloads scan", "stop_scan": "Stop scan", "export": "Export HTML report",
        "quarantine_subtitle": "Quarantine is reversible; permanent deletion requires two confirmations.", "startup_subtitle": "Reversible startup management for your account only.", "boost_subtitle": "Cleans old temporary files only; your important files are untouched.", "history_subtitle": "Recent local NimbleGuard activity, with no data sent online.",
        "refresh": "Refresh list", "quarantine_hint": "Restore only files whose source you know and trust.", "quarantine_empty": "There are no quarantined files.", "restore": "Restore", "permanent_delete": "Delete permanently", "original_location": "Original location",
        "startup_hint": "Disable only an app you know is unnecessary at Windows startup.", "startup_empty": "No startup apps are visible for this account.", "startup_disable": "Disable (reversible)", "disabled_before": "Apps you previously disabled", "registry": "User registry", "startup_folder": "Startup folder",
        "boost_what": "What will happen?", "boost_description": "• Removes temporary files that are at least 12 hours old.\n• Skips locked files, links, and folders; no forced deletion.\n• Limited to 1,500 files or 20 seconds to stay lightweight.", "boost_now": "ϟ Clean safely now", "boost_idle": "This operation is not running in the background.", "history_empty": "No history yet.", "scan_results": "Latest scan results", "scan_ready": "Ready for an on-demand scan",
        "protection_start": "Turn protection on", "protection_stop": "Turn protection off", "defender": "Microsoft Defender protection", "defender_loading": "Checking Microsoft Defender status…", "defender_quick": "Quick system scan", "defender_full": "Full system scan", "defender_update": "Update virus definitions", "defender_note": "Uses the genuine Microsoft Defender engine and Windows signatures.",
        "sidebar_note": "Automatic protection watches Downloads only when enabled.\nNo automatic deletion or heavy permanent scanning.",
    },
    "fr": {
        "language": "Français", "tagline": "Protection intelligente et légère", "dashboard": "Tableau de protection",
        "scan": "Analyse intelligente", "quarantine": "Fichiers isolés", "startup": "Démarrage", "boost": "Nettoyage sûr", "history": "Historique",
        "on_demand": "Analyse à la demande", "shield_on": "Protection téléchargements : active", "shield_off": "Protection téléchargements : arrêtée",
        "dashboard_subtitle": "État clair de l’appareil, sans espace perdu ni analyse continue lourde.",
        "cpu": "Processeur", "memory": "Mémoire RAM", "gpu": "Carte graphique", "disk": "Espace libre",
        "updated": "Actualisation légère toutes les 5 secondes", "hardware": "Informations matériel", "system_disk": "Disque système",
        "download_shield": "Protection téléchargements", "download_shield_info": "Vérifie seulement les nouveaux exécutables dans Downloads toutes les 30 secondes.",
        "switch_on": "Protection active", "switch_off": "Protection arrêtée", "start_scan": "Lancer l’analyse",
        "safe_clean": "Nettoyage sûr", "quick_tools": "Outils rapides", "top_apps": "Applications les plus gourmandes", "top_apps_info": "Affichage seulement — aucune application n’est fermée automatiquement.",
        "scan_subtitle": "Analyse locale explicable ; les cracks ne sont pas automatiquement considérés comme des virus.", "scan_choose": "Choisissez un fichier ou dossier", "scan_file": "Analyser un fichier", "scan_folder": "Choisir un dossier", "quick_scan": "Analyse rapide Downloads", "stop_scan": "Arrêter l’analyse", "export": "Exporter en HTML",
        "quarantine_subtitle": "L’isolement est réversible ; la suppression définitive demande deux confirmations.", "startup_subtitle": "Gestion réversible du démarrage pour votre compte uniquement.", "boost_subtitle": "Nettoie uniquement les fichiers temporaires anciens ; vos fichiers importants restent intacts.", "history_subtitle": "Activité locale récente de NimbleGuard, sans envoi de données en ligne.",
        "refresh": "Actualiser", "quarantine_hint": "Restaurez seulement les fichiers dont vous connaissez et approuvez la source.", "quarantine_empty": "Aucun fichier isolé actuellement.", "restore": "Restaurer", "permanent_delete": "Supprimer définitivement", "original_location": "Emplacement d’origine",
        "startup_hint": "Désactivez uniquement une application que vous savez inutile au démarrage.", "startup_empty": "Aucune application de démarrage visible pour ce compte.", "startup_disable": "Désactiver (réversible)", "disabled_before": "Applications désactivées auparavant", "registry": "Registre utilisateur", "startup_folder": "Dossier Démarrage",
        "boost_what": "Que va-t-il se passer ?", "boost_description": "• Supprime les fichiers temporaires âgés d’au moins 12 heures.\n• Ignore les fichiers verrouillés, liens et dossiers ; aucune suppression forcée.\n• Limite de 1 500 fichiers ou 20 secondes pour rester léger.", "boost_now": "ϟ Nettoyer en sécurité", "boost_idle": "Cette opération ne tourne pas en arrière-plan.", "history_empty": "Aucun historique.", "scan_results": "Résultats de la dernière analyse", "scan_ready": "Prêt pour une analyse à la demande",
        "protection_start": "Activer la protection", "protection_stop": "Arrêter la protection", "defender": "Protection Microsoft Defender", "defender_loading": "Vérification de Microsoft Defender…", "defender_quick": "Analyse rapide du système", "defender_full": "Analyse complète du système", "defender_update": "Mettre à jour les définitions", "defender_note": "Utilise le véritable moteur Microsoft Defender et les signatures Windows.",
        "sidebar_note": "La protection automatique surveille Downloads uniquement lorsqu’elle est active.\nAucune suppression ou analyse lourde continue.",
    },
}


def human_size(size: int) -> str:
    """تحويل الحجم إلى صيغة بسيطة للواجهة."""
    units = ("بايت", "KB", "MB", "GB", "TB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "بايت" else f"{int(value)} {unit}"
        value /= 1024
    return f"{size} بايت"


def is_double_extension(filename: str) -> bool:
    """اكتشاف أسماء مثل photo.jpg.exe التي تستعمل أحياناً لخداع المستخدم."""
    parts = filename.lower().split(".")
    return len(parts) >= 3 and parts[-1] in {ext[1:] for ext in RISKY_EXTENSIONS}


def shannon_entropy(data: bytes) -> float:
    """قياس بسيط لانضغاط/تغليف الملف؛ ليس دليلاً على وجود فيروس بمفرده."""
    if not data:
        return 0.0
    counts = [0] * 256
    for item in data:
        counts[item] += 1
    length = len(data)
    return -sum((count / length) * math.log2(count / length) for count in counts if count)


def sha256_file(file_path: Path, cancel: threading.Event) -> Optional[str]:
    """إنشاء بصمة SHA-256 بكتل صغيرة حتى لا ترتفع الذاكرة."""
    digest = hashlib.sha256()
    try:
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                if cancel.is_set():
                    return None
                digest.update(chunk)
        return digest.hexdigest()
    except (OSError, PermissionError):
        return None


@dataclass
class Verdict:
    path: str
    score: int
    label: str
    reasons: list[str]
    size: int
    sha256: Optional[str]
    modified_at: str


@dataclass
class QuarantineItem:
    """ملف معزول وبياناته اللازمة لاستعادته من دون تخمين."""

    file_path: Path
    metadata_path: Path
    metadata: dict


@dataclass
class StartupEntry:
    """مدخل بدء تشغيل للمستخدم الحالي فقط، لا يشمل خدمات النظام."""

    source: str
    name: str
    command: str
    location: str


class RiskEngine:
    """محرك قواعد محلي ومفسّر؛ كل نتيجة تحتوي سببها ولا تستخدم نموذجاً غامضاً."""

    @staticmethod
    def inspect(file_path: Path, cancel: threading.Event) -> Optional[Verdict]:
        try:
            stat = file_path.stat()
            if not file_path.is_file() or file_path.is_symlink():
                return None
            size = stat.st_size
        except (OSError, PermissionError):
            return None

        name = file_path.name.lower()
        suffix = file_path.suffix.lower()
        normalized_path = str(file_path).lower()
        score = 0
        reasons: list[str] = []
        is_crack = any(word in name for word in CRACK_WORDS)
        has_malware_name = any(word in name for word in MALWARE_WORDS)

        if suffix in RISKY_EXTENSIONS:
            score += 15
            reasons.append(f"امتداد قابل للتشغيل أو البرمجة: {suffix}")
        if is_double_extension(name):
            score += 25
            reasons.append("اسم بامتداد مزدوج قد يُخفي الامتداد الحقيقي")
        if is_crack:
            score += 12
            reasons.append("اسم يشير إلى كراك أو مُفعّل؛ راجع مصدر الملف")
        if has_malware_name:
            score += 38
            reasons.append("اسم يحتوي مؤشراً شائعاً لبرمجيات ضارة")
        if suffix in RISKY_EXTENSIONS and any(
            part in normalized_path for part in ("\\appdata\\local\\temp", "\\downloads\\", "\\startup")
        ):
            score += 12
            reasons.append("ملف قابل للتشغيل في مسار شائع للملفات المؤقتة أو التنزيلات")

        sample = b""
        try:
            with file_path.open("rb") as handle:
                sample = handle.read(SAMPLE_SIZE)
        except (OSError, PermissionError):
            reasons.append("تعذر قراءة جزء من الملف؛ يلزم فحصه بمضاد الفيروسات")
            score += 8

        lower_sample = sample.lower()
        if sample.startswith(b"MZ") and suffix not in EXECUTABLE_EXTENSIONS:
            score += 25
            reasons.append("توقيع ملف تنفيذي لا يطابق امتداده الظاهر")
        if suffix in {".ps1", ".bat", ".cmd", ".vbs", ".js", ".hta"}:
            matching_markers = sum(marker in lower_sample for marker in SCRIPT_MARKERS)
            if matching_markers:
                score += min(30, matching_markers * 10)
                reasons.append("السكربت يتضمن أوامر تنزيل/تشغيل مخفية شائعة")
        if suffix in EXECUTABLE_EXTENSIONS and sample and shannon_entropy(sample) > 7.65:
            score += 8
            reasons.append("الملف عالي التغليف/الضغط؛ ليس دليلاً حاسماً بمفرده")

        # ملفات الكراك ليست مرادفاً للفيروس: نميّزها إذا لم تتجمع مؤشرات عالية أخرى.
        if score >= 60:
            label = "خطر مرتفع"
        elif is_crack and score >= 20:
            label = "كراك أو لعبة معدّلة — مراجعة"
        elif score >= 30:
            label = "مريب — يحتاج مراجعة"
        elif score > 0:
            label = "مؤشرات محدودة"
        else:
            label = "لا توجد مؤشرات محلية واضحة"

        # لا نحسب الهاش للملفات الضخمة حفاظاً على سرعة القرص والبطارية.
        digest = sha256_file(file_path, cancel) if size <= MAX_HASH_SIZE else None
        if size > MAX_HASH_SIZE:
            reasons.append("لم تُنشأ البصمة لأن الحجم كبير؛ الفحص بقي محدود الموارد")
        if not reasons:
            reasons.append("لم تطابق قواعد الاشتباه المحلية أي مؤشر")

        return Verdict(
            path=str(file_path),
            score=min(score, 100),
            label=label,
            reasons=reasons,
            size=size,
            sha256=digest,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).astimezone().isoformat(timespec="seconds"),
        )


class Storage:
    """تخزين صغير للسجل والملفات المعزولة ضمن حساب المستخدم فقط."""

    @staticmethod
    def ensure() -> None:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def append_history(entry: dict) -> None:
        Storage.ensure()
        data: list[dict] = []
        try:
            if HISTORY_FILE.exists():
                data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
                if not isinstance(data, list):
                    data = []
        except (OSError, json.JSONDecodeError):
            data = []
        data.append(entry)
        # الاحتفاظ بآخر 100 عملية فقط لمنع تضخم ملف السجل.
        HISTORY_FILE.write_text(json.dumps(data[-100:], ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def read_history() -> list[dict]:
        try:
            raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    @staticmethod
    def quarantine(source: Path, verdict: Verdict) -> Path:
        """عزل اختياري: نقل الملف فقط بعد ضغط المستخدم للزر، بلا حذف نهائي."""
        Storage.ensure()
        if not source.exists() or not source.is_file():
            raise FileNotFoundError("الملف لم يعد موجوداً في موقعه الأصلي")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = QUARANTINE_DIR / f"{stamp}_{source.name}"
        counter = 1
        while destination.exists():
            destination = QUARANTINE_DIR / f"{stamp}_{counter}_{source.name}"
            counter += 1
        shutil.move(str(source), str(destination))
        metadata = destination.with_suffix(destination.suffix + ".json")
        metadata.write_text(json.dumps(asdict(verdict), ensure_ascii=False, indent=2), encoding="utf-8")
        return destination

    @staticmethod
    def list_quarantine() -> list[QuarantineItem]:
        """قراءة العزل فقط؛ لا يتغير أي ملف لمجرد فتح صفحة العزل."""
        Storage.ensure()
        items: list[QuarantineItem] = []
        try:
            for file_path in QUARANTINE_DIR.iterdir():
                if not file_path.is_file() or file_path.name.endswith(".json"):
                    continue
                metadata_path = file_path.with_suffix(file_path.suffix + ".json")
                metadata: dict = {}
                try:
                    if metadata_path.exists():
                        raw = json.loads(metadata_path.read_text(encoding="utf-8"))
                        metadata = raw if isinstance(raw, dict) else {}
                except (OSError, json.JSONDecodeError):
                    metadata = {}
                items.append(QuarantineItem(file_path, metadata_path, metadata))
        except OSError:
            return []
        def modified_time(item: QuarantineItem) -> float:
            try:
                return item.file_path.stat().st_mtime
            except OSError:
                return 0.0

        return sorted(items, key=modified_time, reverse=True)

    @staticmethod
    def restore_quarantine(item: QuarantineItem, destination_dir: Optional[Path] = None) -> Path:
        """استعادة الملف إلى مكانه الأصلي أو لمجلد اختاره المستخدم، دون استبدال ملف موجود."""
        original = Path(str(item.metadata.get("path", item.file_path.name)))
        target = (destination_dir / original.name) if destination_dir else original
        if target.exists():
            raise FileExistsError("يوجد ملف بالاسم نفسه في وجهة الاستعادة")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(item.file_path), str(target))
        try:
            item.metadata_path.unlink(missing_ok=True)
        except OSError:
            pass
        return target

    @staticmethod
    def delete_quarantined(item: QuarantineItem) -> None:
        """حذف نهائي لا يُستدعى إلا بعد تأكيد المستخدم مرتين من الواجهة."""
        item.file_path.unlink()
        item.metadata_path.unlink(missing_ok=True)


class StartupManager:
    """إدارة محدودة وآمنة لبرامج بدء تشغيل حساب المستخدم الحالي فقط."""

    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    @staticmethod
    def _load_disabled() -> list[dict]:
        try:
            raw = json.loads(STARTUP_BACKUP_FILE.read_text(encoding="utf-8"))
            return raw if isinstance(raw, list) else []
        except (OSError, json.JSONDecodeError):
            return []

    @staticmethod
    def _save_disabled(entries: list[dict]) -> None:
        Storage.ensure()
        STARTUP_BACKUP_FILE.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def list_entries() -> list[StartupEntry]:
        entries: list[StartupEntry] = []
        if winreg is not None:
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, StartupManager.RUN_KEY, 0, winreg.KEY_READ) as key:
                    index = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, index)
                            index += 1
                            if isinstance(value, str):
                                entries.append(StartupEntry("registry", name, value, StartupManager.RUN_KEY))
                        except OSError:
                            break
            except OSError:
                pass

        startup_dir = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        try:
            for item in startup_dir.iterdir():
                if item.is_file() and not item.name.endswith(".nimbleguard-disabled"):
                    entries.append(StartupEntry("folder", item.name, str(item), str(item)))
        except OSError:
            pass
        return sorted(entries, key=lambda item: item.name.lower())

    @staticmethod
    def list_disabled() -> list[dict]:
        return StartupManager._load_disabled()

    @staticmethod
    def disable(entry: StartupEntry) -> None:
        """تعطيل قابل للاسترجاع؛ لا نحذف أو نوقف أي عملية تعمل حالياً."""
        disabled = StartupManager._load_disabled()
        record = asdict(entry) | {"disabled_at": datetime.now().isoformat(timespec="seconds")}
        if entry.source == "registry":
            if winreg is None:
                raise RuntimeError("إدارة سجل Windows غير متاحة")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, StartupManager.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, entry.name)
        else:
            source = Path(entry.location)
            disabled_path = source.with_name(source.name + ".nimbleguard-disabled")
            if disabled_path.exists():
                raise FileExistsError("توجد نسخة معطلة بالاسم نفسه")
            source.rename(disabled_path)
            record["disabled_path"] = str(disabled_path)
        disabled.append(record)
        StartupManager._save_disabled(disabled)

    @staticmethod
    def restore(record: dict) -> None:
        """إرجاع مدخل سبق تعطيله، ثم حذف سجل النسخة المعطلة فقط بعد النجاح."""
        if record.get("source") == "registry":
            if winreg is None:
                raise RuntimeError("إدارة سجل Windows غير متاحة")
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, StartupManager.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, str(record["name"]), 0, winreg.REG_SZ, str(record["command"]))
        else:
            disabled_path = Path(str(record.get("disabled_path", "")))
            original_path = Path(str(record.get("location", "")))
            if original_path.exists():
                raise FileExistsError("يوجد ملف في موضع بدء التشغيل بالفعل")
            disabled_path.rename(original_path)
        remaining = [item for item in StartupManager._load_disabled() if item != record]
        StartupManager._save_disabled(remaining)


class NimbleGuardApp(ctk.CTk):
    """واجهة سطح مكتب خفيفة؛ العمليات البطيئة تعمل في خيط منفصل عن الواجهة."""

    COLORS = {
        "bg": "#0B1220", "panel": "#111C2E", "panel_hover": "#18263C",
        "accent": "#31C48D", "accent_hover": "#20996A", "danger": "#F05252",
        "text": "#EDF2F7", "muted": "#94A3B8", "warning": "#F59E0B",
    }

    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION} | حماية ذكية خفيفة")
        self.geometry("1180x750")
        self.minsize(980, 650)
        self.configure(fg_color=self.COLORS["bg"])
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.active_page = "dashboard"
        self.language_code = "ar"
        self.protection_enabled = False
        self.monitor_generation = 0
        self.download_snapshot: dict[str, tuple[float, int]] = {}
        self.gpu_name = "جارٍ التعرّف على كرت الشاشة…"
        self.defender_info = {"label": "جارٍ التحقق من Microsoft Defender…", "enabled": False}
        self.defender_scan_running = False
        self.results: list[Verdict] = []
        self.signature_status: dict[str, str] = {}
        self.current_scan_cancel = threading.Event()
        self.worker_queue: queue.Queue[tuple] = queue.Queue()
        self.busy = False

        self._build_layout()
        self.show_page("dashboard")
        self.after(250, self._process_worker_events)
        self.after(1_500, self._refresh_metrics)
        self._run_background("gpu", self._load_gpu_info)
        self._run_background("defender_status", self._load_defender_status)

    def t(self, key: str) -> str:
        """إرجاع النص بالواجهة المختارة، مع العربية كنسخة احتياطية آمنة."""
        return TRANSLATIONS.get(self.language_code, TRANSLATIONS["ar"]).get(key, TRANSLATIONS["ar"].get(key, key))

    def _build_layout(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=245, corner_radius=0, fg_color="#0D1728")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        ctk.CTkLabel(
            self.sidebar, text="◈  NimbleGuard", font=ctk.CTkFont(size=25, weight="bold"),
            text_color=self.COLORS["text"],
        ).pack(padx=20, pady=(30, 5), anchor="e")
        self.brand_subtitle = ctk.CTkLabel(
            self.sidebar, text=self.t("tagline"), font=ctk.CTkFont(size=13),
            text_color=self.COLORS["muted"],
        )
        self.brand_subtitle.pack(padx=20, pady=(0, 35), anchor="e")

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        nav_items = [
            ("dashboard", "⌂", "dashboard"),
            ("scan", "◉", "scan"),
            ("quarantine", "▣", "quarantine"),
            ("startup", "↗", "startup"),
            ("boost", "ϟ", "boost"),
            ("history", "▤", "history"),
        ]
        self.nav_icons: dict[str, str] = {}
        for page, icon, text_key in nav_items:
            button = ctk.CTkButton(
                self.sidebar, text=f"{icon}  {self.t(text_key)}", anchor="e", height=50, corner_radius=10,
                fg_color="#14243B", hover_color="#263D5C", border_width=1, border_color="#2B405E",
                text_color=self.COLORS["text"], font=ctk.CTkFont(size=16, weight="bold"), command=lambda p=page: self.show_page(p),
            )
            button.pack(fill="x", padx=14, pady=5)
            self.nav_buttons[page] = button
            self.nav_icons[page] = icon

        self.sidebar_note = ctk.CTkLabel(
            self.sidebar,
            text=self.t("sidebar_note"),
            justify="right", anchor="e", text_color=self.COLORS["muted"], font=ctk.CTkFont(size=13),
        )
        self.sidebar_note.pack(side="bottom", fill="x", padx=18, pady=25)

        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=self.COLORS["bg"])
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(self.content, height=78, corner_radius=0, fg_color="#0D1728")
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(0, weight=1)
        self.page_title = ctk.CTkLabel(top, text="", font=ctk.CTkFont(size=22, weight="bold"), anchor="e")
        self.page_title.grid(row=0, column=0, padx=28, pady=20, sticky="e")
        self.health_badge = ctk.CTkLabel(
            top, text="● " + self.t("shield_off"), text_color=self.COLORS["warning"],
            fg_color="#103829", corner_radius=12, padx=12, pady=6,
        )
        self.health_badge.grid(row=0, column=1, padx=26, pady=20, sticky="w")
        self.language_selector = ctk.CTkOptionMenu(
            top, values=["العربية", "Français", "English"], width=105, height=30,
            fg_color="#2C3E57", button_color="#3A506E", command=self._change_language,
        )
        self.language_selector.set("العربية")
        self.language_selector.grid(row=0, column=2, padx=(0, 20), pady=20, sticky="w")
        self.page_host = ctk.CTkFrame(self.content, fg_color="transparent")
        self.page_host.grid(row=1, column=0, sticky="nsew", padx=28, pady=24)
        self.page_host.grid_columnconfigure(0, weight=1)
        # كانت الصفّة 0 تتمدّد فتخلق مساحة فارغة ضخمة أعلى كل صفحة.
        self.page_host.grid_rowconfigure(0, weight=0)
        self.page_host.grid_rowconfigure(1, weight=1)

    def _change_language(self, label: str) -> None:
        code_by_label = {"العربية": "ar", "Français": "fr", "English": "en"}
        self.language_code = code_by_label.get(label, "ar")
        self.brand_subtitle.configure(text=self.t("tagline"))
        self.sidebar_note.configure(text=self.t("sidebar_note"))
        for page, button in self.nav_buttons.items():
            button.configure(text=f"{self.nav_icons[page]}  {self.t(page)}")
        self._update_protection_badge()
        self.show_page(self.active_page)

    def _update_protection_badge(self) -> None:
        enabled = self.protection_enabled
        self.health_badge.configure(
            text="● " + self.t("shield_on" if enabled else "shield_off"),
            text_color=self.COLORS["accent"] if enabled else self.COLORS["warning"],
            fg_color="#103829" if enabled else "#3A2B10",
        )

    def _clear_page(self) -> None:
        for child in self.page_host.winfo_children():
            child.destroy()

    def show_page(self, page: str) -> None:
        if self.busy and page == "scan":
            # يسمح بالتنقل لباقي الصفحات، لكن لا يبدأ مسحاً ثانياً متزامناً.
            pass
        self.active_page = page
        for name, button in self.nav_buttons.items():
            button.configure(
                fg_color="#2563A8" if name == page else "#14243B",
                border_color="#4EA1ED" if name == page else "#2B405E",
            )
        self._clear_page()
        builders = {
            "dashboard": self._build_dashboard,
            "scan": self._build_scan_page,
            "quarantine": self._build_quarantine_page,
            "startup": self._build_startup_page,
            "boost": self._build_boost_page,
            "history": self._build_history_page,
        }
        builders[page]()

    def _section_title(self, title: str, subtitle: str) -> None:
        self.page_title.configure(text=title)
        ctk.CTkLabel(
            self.page_host, text=subtitle, anchor="e", justify="right",
            font=ctk.CTkFont(size=14), text_color=self.COLORS["muted"],
        ).grid(row=0, column=0, sticky="ew", pady=(0, 16))

    def _card(self, parent, **kwargs) -> ctk.CTkFrame:
        return ctk.CTkFrame(parent, corner_radius=16, fg_color=self.COLORS["panel"], **kwargs)

    def _build_dashboard(self) -> None:
        self._section_title(self.t("dashboard"), self.t("dashboard_subtitle"))
        body = ctk.CTkFrame(self.page_host, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.cpu_value, self.cpu_bar, _ = self._resource_card(body, 0, "CPU", self.t("cpu"), self.t("updated"), "#38BDF8")
        self.memory_value, self.memory_bar, _ = self._resource_card(body, 1, "RAM", self.t("memory"), self.t("updated"), "#A78BFA")
        self.gpu_value, self.gpu_bar, self.gpu_caption = self._resource_card(body, 2, "GPU", self.t("gpu"), self.t("hardware"), "#F59E0B")
        self.disk_value, self.disk_bar, _ = self._resource_card(body, 3, "SSD", self.t("disk"), self.t("system_disk"), "#31C48D")

        shield_card = self._card(body)
        shield_card.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(18, 0), padx=(0, 7))
        shield_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            shield_card, text=self.t("download_shield"), anchor="e", font=ctk.CTkFont(size=19, weight="bold"),
        ).grid(row=0, column=0, padx=22, pady=(18, 3), sticky="e")
        self.protection_status_label = ctk.CTkLabel(
            shield_card, text=self.t("download_shield_info"), anchor="e", justify="right", text_color=self.COLORS["muted"],
        )
        self.protection_status_label.grid(row=1, column=0, padx=22, pady=(0, 12), sticky="e")
        protection_buttons = ctk.CTkFrame(shield_card, fg_color="transparent")
        protection_buttons.grid(row=2, column=0, padx=22, pady=(0, 18), sticky="e")
        self.protection_on_button = ctk.CTkButton(
            protection_buttons, text="● " + self.t("protection_start"), width=165, height=38,
            fg_color=self.COLORS["accent"], hover_color=self.COLORS["accent_hover"], command=lambda: self._set_protection(True),
        )
        self.protection_on_button.pack(side="right", padx=(8, 0))
        self.protection_off_button = ctk.CTkButton(
            protection_buttons, text="■ " + self.t("protection_stop"), width=155, height=38,
            fg_color="#34445B", hover_color="#4A5E78", command=lambda: self._set_protection(False),
        )
        self.protection_off_button.pack(side="right")

        defender_card = self._card(body)
        defender_card.grid(row=1, column=2, columnspan=2, sticky="nsew", pady=(18, 0), padx=(7, 0))
        defender_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(defender_card, text=self.t("defender"), anchor="e", font=ctk.CTkFont(size=19, weight="bold")).grid(
            row=0, column=0, padx=22, pady=(18, 3), sticky="e"
        )
        self.defender_status_label = ctk.CTkLabel(
            defender_card, text=self.defender_info["label"], anchor="e", justify="right", text_color=self.COLORS["muted"],
        )
        self.defender_status_label.grid(row=1, column=0, padx=22, pady=(0, 12), sticky="e")
        defender_buttons = ctk.CTkFrame(defender_card, fg_color="transparent")
        defender_buttons.grid(row=2, column=0, padx=22, pady=(0, 18), sticky="e")
        self.defender_quick_button = ctk.CTkButton(defender_buttons, text=self.t("defender_quick"), width=150, height=38, fg_color="#3478C8", hover_color="#245A9B", command=lambda: self._start_defender_scan("QuickScan"))
        self.defender_quick_button.pack(side="right", padx=(8, 0))
        self.defender_full_button = ctk.CTkButton(defender_buttons, text=self.t("defender_full"), width=150, height=38, fg_color="#8B5CF6", hover_color="#6D3FD4", command=lambda: self._start_defender_scan("FullScan"))
        self.defender_full_button.pack(side="right", padx=(8, 0))
        self.defender_update_button = ctk.CTkButton(defender_buttons, text="↻", width=40, height=38, fg_color="#34445B", hover_color="#4A5E78", command=self._update_defender_signatures)
        self.defender_update_button.pack(side="right")

        action_card = self._card(body)
        action_card.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(14, 0))
        action_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            action_card, text=self.t("quick_tools"), anchor="e", font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=22, pady=(14, 8), sticky="e")
        buttons = ctk.CTkFrame(action_card, fg_color="transparent")
        buttons.grid(row=1, column=0, padx=22, pady=(0, 15), sticky="e")
        ctk.CTkButton(buttons, text=self.t("start_scan"), width=165, height=40, corner_radius=10, fg_color=self.COLORS["accent"], hover_color=self.COLORS["accent_hover"], command=lambda: self.show_page("scan")).pack(side="right", padx=(9, 0))
        ctk.CTkButton(buttons, text=self.t("safe_clean"), width=140, height=40, corner_radius=10, fg_color=self.COLORS["panel_hover"], command=lambda: self.show_page("boost")).pack(side="right")

        process_card = self._card(body)
        process_card.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(14, 0))
        process_card.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            process_card, text=self.t("top_apps"), anchor="e",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(16, 4), sticky="e")
        self.top_processes_label = ctk.CTkLabel(
            process_card, text=self.t("top_apps_info"), anchor="e", justify="right",
            text_color=self.COLORS["muted"], font=ctk.CTkFont(size=13),
        )
        self.top_processes_label.grid(row=1, column=0, padx=20, pady=(0, 16), sticky="ew")
        self._update_protection_card()
        self._update_defender_card()

    def _resource_card(self, parent, column: int, badge: str, title: str, caption: str, color: str) -> tuple[ctk.CTkLabel, ctk.CTkProgressBar, ctk.CTkLabel]:
        """بطاقة عتاد مرئية: شارة الجهاز، الرقم، وشريط مستوى مثل شحن البطارية."""
        card = self._card(parent)
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 7, 0 if column == 3 else 7))
        heading = ctk.CTkFrame(card, fg_color="transparent")
        heading.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(heading, text=badge, width=42, height=24, corner_radius=7, fg_color=color, text_color="#07111F", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        ctk.CTkLabel(heading, text=title, text_color=self.COLORS["muted"], anchor="e").pack(side="right")
        value_label = ctk.CTkLabel(card, text="—", font=ctk.CTkFont(size=25, weight="bold"), anchor="e")
        value_label.pack(fill="x", padx=16, anchor="e")
        bar = ctk.CTkProgressBar(card, height=9, corner_radius=8, progress_color=color, fg_color="#25364D")
        bar.pack(fill="x", padx=16, pady=(8, 8))
        bar.set(0)
        caption_label = ctk.CTkLabel(card, text=caption, text_color=self.COLORS["muted"], font=ctk.CTkFont(size=11), anchor="e")
        caption_label.pack(fill="x", padx=16, pady=(0, 15))
        return value_label, bar, caption_label

    def _build_scan_page(self) -> None:
        self._section_title(self.t("scan"), self.t("scan_subtitle"))
        holder = ctk.CTkFrame(self.page_host, fg_color="transparent")
        holder.grid(row=1, column=0, sticky="nsew")
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(2, weight=1)

        control = self._card(holder)
        control.grid(row=0, column=0, sticky="ew")
        control.grid_columnconfigure(0, weight=1)
        self.scan_path_label = ctk.CTkLabel(
            control, text=self.t("scan_choose"), anchor="e", text_color=self.COLORS["muted"],
        )
        self.scan_path_label.grid(row=0, column=0, padx=20, pady=18, sticky="e")
        control_actions = ctk.CTkFrame(control, fg_color="transparent")
        control_actions.grid(row=1, column=0, padx=20, pady=(0, 18), sticky="e")
        self.scan_quick_button = ctk.CTkButton(
            control_actions, text=self.t("quick_scan"), width=155, command=self._quick_scan,
            fg_color="#2C3E57",
        )
        self.scan_quick_button.pack(side="right", padx=(8, 0))
        self.scan_file_button = ctk.CTkButton(
            control_actions, text=self.t("scan_file"), width=115, command=self._choose_file_and_scan,
            fg_color=self.COLORS["panel_hover"],
        )
        self.scan_file_button.pack(side="right", padx=(8, 0))
        self.scan_folder_button = ctk.CTkButton(
            control_actions, text=self.t("scan_folder"), width=165, command=self._choose_folder_and_scan,
            fg_color=self.COLORS["accent"], hover_color=self.COLORS["accent_hover"],
        )
        self.scan_folder_button.pack(side="right")
        self.cancel_button = ctk.CTkButton(
            control_actions, text=self.t("stop_scan"), width=110, command=self._cancel_scan,
            fg_color=self.COLORS["danger"], state="disabled",
        )
        self.cancel_button.pack(side="right", padx=(0, 8))

        self.scan_progress = ctk.CTkProgressBar(holder, progress_color=self.COLORS["accent"])
        self.scan_progress.grid(row=1, column=0, sticky="ew", pady=(16, 8))
        self.scan_progress.set(0)
        self.scan_status = ctk.CTkLabel(holder, text=self.t("scan_ready"), anchor="e", text_color=self.COLORS["muted"])
        self.scan_status.grid(row=1, column=0, sticky="e", padx=8, pady=(15, 6))

        results_card = self._card(holder)
        results_card.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        results_card.grid_columnconfigure(0, weight=1)
        results_card.grid_rowconfigure(1, weight=1)
        self.results_heading = ctk.CTkLabel(results_card, text=self.t("scan_results"), anchor="e", font=ctk.CTkFont(size=16, weight="bold"))
        self.results_heading.grid(row=0, column=0, padx=18, pady=(16, 8), sticky="e")
        self.export_report_button = ctk.CTkButton(
            results_card, text=self.t("export"), width=135, height=30,
            fg_color="#2C3E57", command=self._export_report,
        )
        self.export_report_button.grid(row=0, column=1, padx=16, pady=(14, 8), sticky="w")
        self.results_frame = ctk.CTkScrollableFrame(results_card, fg_color="transparent")
        self.results_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 12))
        self._render_results()

    def _choose_file_and_scan(self) -> None:
        selected = filedialog.askopenfilename(title="اختر ملفاً للفحص")
        if selected:
            self._start_scan(Path(selected))

    def _choose_folder_and_scan(self) -> None:
        selected = filedialog.askdirectory(title="اختر مجلداً للفحص")
        if selected:
            self._start_scan(Path(selected))

    def _quick_scan(self) -> None:
        """فحص سريع لمجلد التنزيلات فقط؛ نطاق واضح وخفيف للمستخدم."""
        downloads = Path.home() / "Downloads"
        if not downloads.is_dir():
            messagebox.showinfo(APP_NAME, "لم يُعثر على مجلد Downloads في حسابك.")
            return
        self._start_scan(downloads)

    def _start_scan(self, target: Path) -> None:
        if self.busy:
            messagebox.showinfo(APP_NAME, "توجد عملية تعمل الآن. انتظر حتى تنتهي أو أوقفها أولاً.")
            return
        self.results = []
        self.signature_status = {}
        self.current_scan_cancel = threading.Event()
        self.busy = True
        if hasattr(self, "scan_path_label"):
            self.scan_path_label.configure(text=str(target))
            self.scan_file_button.configure(state="disabled")
            self.scan_folder_button.configure(state="disabled")
            self.scan_quick_button.configure(state="disabled")
            self.cancel_button.configure(state="normal")
            self.scan_progress.set(0)
        self._run_background("scan", lambda: self._scan_target(target))

    def _scan_target(self, target: Path) -> None:
        found: list[Verdict] = []
        inspected = 0
        skipped = 0
        total_hint = 1

        if target.is_file():
            paths: Iterable[Path] = [target]
        else:
            paths = self._iter_files_limited(target)
            total_hint = MAX_FILES_PER_SCAN

        for file_path in paths:
            if self.current_scan_cancel.is_set():
                break
            inspected += 1
            verdict = RiskEngine.inspect(file_path, self.current_scan_cancel)
            if verdict is None:
                skipped += 1
            elif verdict.score > 0:
                found.append(verdict)
                self.worker_queue.put(("result", verdict))
            if inspected == 1 or inspected % 8 == 0:
                self.worker_queue.put(("progress", inspected, total_hint, file_path.name))

        cancelled = self.current_scan_cancel.is_set()
        event = {
            "kind": "فحص ذكي", "at": datetime.now().isoformat(timespec="seconds"),
            "target": str(target), "files": inspected, "findings": len(found),
            "cancelled": cancelled,
        }
        try:
            Storage.append_history(event)
        except OSError:
            pass
        self.worker_queue.put(("scan_done", found, inspected, skipped, cancelled))

    @staticmethod
    def _iter_files_limited(root: Path) -> Iterable[Path]:
        """استكشاف بدون اتباع الروابط الرمزية، وبعدد أقصى لحماية أداء الجهاز."""
        stack = [root]
        sent = 0
        while stack and sent < MAX_FILES_PER_SCAN:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        if sent >= MAX_FILES_PER_SCAN:
                            return
                        try:
                            if entry.is_symlink():
                                continue
                            path = Path(entry.path)
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(path)
                            elif entry.is_file(follow_symlinks=False):
                                sent += 1
                                yield path
                        except OSError:
                            continue
            except (OSError, PermissionError):
                continue

    def _cancel_scan(self) -> None:
        if self.busy:
            self.current_scan_cancel.set()
            self.scan_status.configure(text="جارٍ إيقاف الفحص بأمان…")
            self.cancel_button.configure(state="disabled")

    def _render_results(self) -> None:
        if not hasattr(self, "results_frame"):
            return
        for widget in self.results_frame.winfo_children():
            widget.destroy()
        if not self.results:
            ctk.CTkLabel(
                self.results_frame, text="لا توجد نتائج للعرض. اختر موقعاً لبدء الفحص.",
                text_color=self.COLORS["muted"], anchor="e",
            ).pack(fill="x", padx=10, pady=22)
            return
        for verdict in sorted(self.results, key=lambda item: item.score, reverse=True):
            self._result_row(verdict)

    def _result_row(self, verdict: Verdict) -> None:
        color = self.COLORS["danger"] if verdict.score >= 60 else self.COLORS["warning"] if verdict.score >= 30 else self.COLORS["accent"]
        row = ctk.CTkFrame(self.results_frame, fg_color="#16243A", corner_radius=10)
        row.pack(fill="x", padx=2, pady=5)
        row.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            row, text=f"{verdict.label}  •  {verdict.score}/100", text_color=color,
            font=ctk.CTkFont(weight="bold"), anchor="e",
        ).grid(row=0, column=0, padx=14, pady=(11, 2), sticky="e")
        ctk.CTkLabel(row, text=verdict.path, text_color=self.COLORS["text"], anchor="e", justify="right").grid(
            row=1, column=0, padx=14, sticky="ew"
        )
        ctk.CTkLabel(
            row, text="؛ ".join(verdict.reasons[:2]), text_color=self.COLORS["muted"],
            anchor="e", justify="right", wraplength=650, font=ctk.CTkFont(size=12),
        ).grid(row=2, column=0, padx=14, pady=(2, 11), sticky="e")
        signature_text = self.signature_status.get(verdict.path)
        if signature_text:
            ctk.CTkLabel(
                row, text=signature_text, text_color=self.COLORS["muted"], anchor="e",
                font=ctk.CTkFont(size=12),
            ).grid(row=3, column=0, padx=14, pady=(0, 10), sticky="e")

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=4, padx=12, pady=12)
        ctk.CTkButton(
            actions, text="فحص التوقيع", width=105, height=28, fg_color="#2C3E57",
            command=lambda v=verdict: self._verify_signature(v),
        ).pack(pady=(0, 6))
        if verdict.score >= 30:
            ctk.CTkButton(
                actions, text="عزل اختياري", width=105, height=28, fg_color="#2C3E57",
                command=lambda v=verdict: self._confirm_quarantine(v),
            ).pack()

    def _verify_signature(self, verdict: Verdict) -> None:
        """التحقق عند الطلب فقط؛ لا نستدعي PowerShell لآلاف الملفات أثناء الفحص."""
        file_path = Path(verdict.path)
        if not file_path.exists():
            messagebox.showwarning(APP_NAME, "الملف لم يعد موجوداً في موقعه.")
            return
        self.signature_status[verdict.path] = "جارٍ التحقق من التوقيع…"
        self._render_results()
        self._run_background("signature", lambda: self._signature_worker(file_path))

    def _signature_worker(self, file_path: Path) -> None:
        # نعالج علامة الاقتباس داخل المسار قبل إدخاله في نص PowerShell.
        escaped_path = str(file_path).replace("'", "''")
        script = (
            f"$s=Get-AuthenticodeSignature -LiteralPath '{escaped_path}';"
            "$subject=if($s.SignerCertificate){$s.SignerCertificate.Subject}else{''};"
            "Write-Output ($s.Status.ToString() + '|' + $subject)"
        )
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12, check=False,
            )
            output = completed.stdout.strip()
            if not output:
                detail = "تعذر قراءة حالة التوقيع"
            else:
                status, _, subject = output.partition("|")
                labels = {
                    "Valid": "توقيع صالح",
                    "NotSigned": "الملف غير موقّع",
                    "HashMismatch": "التوقيع غير صالح أو تغيّر الملف",
                    "NotTrusted": "التوقيع موجود لكن الناشر غير موثوق",
                }
                detail = labels.get(status, f"حالة التوقيع: {status}")
                if subject and status == "Valid":
                    detail += f" — {subject[:70]}"
        except (OSError, subprocess.SubprocessError):
            detail = "تعذر تشغيل فحص توقيع Windows"
        self.worker_queue.put(("signature_done", str(file_path), detail))

    def _export_report(self) -> None:
        """تصدير تقرير HTML محلي؛ لا تُرسل النتائج إلى أي موقع."""
        if not self.results:
            messagebox.showinfo(APP_NAME, "لا توجد نتائج مشتبه بها لتصديرها بعد.")
            return
        selected = filedialog.asksaveasfilename(
            title="حفظ تقرير الفحص", defaultextension=".html",
            filetypes=[("تقرير HTML", "*.html")], initialfile="nimbleguard-report.html",
        )
        if not selected:
            return
        rows = []
        for verdict in sorted(self.results, key=lambda item: item.score, reverse=True):
            reasons = "<br>".join(html.escape(reason) for reason in verdict.reasons)
            signature = html.escape(self.signature_status.get(verdict.path, "لم يتم التحقق"))
            rows.append(
                "<tr>"
                f"<td>{html.escape(verdict.label)}</td><td>{verdict.score}/100</td>"
                f"<td>{html.escape(verdict.path)}</td><td>{reasons}</td>"
                f"<td>{signature}</td>"
                "</tr>"
            )
        document = f"""<!doctype html><html lang=\"ar\" dir=\"rtl\"><head><meta charset=\"utf-8\">
<title>NimbleGuard Scan Report</title><style>
body{{font-family:Segoe UI,Tahoma,sans-serif;background:#0b1220;color:#edf2f7;padding:32px}}
table{{border-collapse:collapse;width:100%;background:#111c2e}}th,td{{border:1px solid #314158;padding:10px;text-align:right;vertical-align:top}}
th{{background:#18263c}}.muted{{color:#94a3b8}}</style></head><body>
<h1>NimbleGuard — تقرير فحص محلي</h1><p class=\"muted\">وقت الإنشاء: {html.escape(datetime.now().isoformat(timespec='seconds'))} | النتائج: {len(self.results)}</p>
<table><thead><tr><th>التصنيف</th><th>الدرجة</th><th>الملف</th><th>الأسباب</th><th>التوقيع</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table><p class=\"muted\">هذا تقرير مؤشرات محلية، وليس حكماً نهائياً على الملف.</p></body></html>"""
        try:
            Path(selected).write_text(document, encoding="utf-8")
            Storage.append_history({"kind": "تصدير تقرير", "at": datetime.now().isoformat(timespec="seconds"), "target": selected})
            messagebox.showinfo(APP_NAME, f"تم حفظ التقرير:\n{selected}")
        except OSError as error:
            messagebox.showerror(APP_NAME, f"تعذر حفظ التقرير:\n{error}")

    def _confirm_quarantine(self, verdict: Verdict) -> None:
        answer = messagebox.askyesno(
            "تأكيد العزل",
            "سيُنقل الملف إلى مجلد عزل NimbleGuard ويمكن استعادته يدوياً لاحقاً.\n\n"
            f"الملف: {verdict.path}\n\nهل تريد المتابعة؟",
        )
        if not answer:
            return
        try:
            destination = Storage.quarantine(Path(verdict.path), verdict)
            self.results = [item for item in self.results if item.path != verdict.path]
            self._render_results()
            Storage.append_history({
                "kind": "عزل ملف", "at": datetime.now().isoformat(timespec="seconds"),
                "target": verdict.path, "destination": str(destination),
            })
            messagebox.showinfo(APP_NAME, f"تم عزل الملف بنجاح:\n{destination}")
        except (OSError, FileNotFoundError, shutil.Error) as error:
            messagebox.showerror(APP_NAME, f"تعذر عزل الملف:\n{error}")

    def _build_quarantine_page(self) -> None:
        self._section_title(self.t("quarantine"), self.t("quarantine_subtitle"))
        card = self._card(self.page_host)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        controls = ctk.CTkFrame(card, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        ctk.CTkButton(
            controls, text=self.t("refresh"), width=120, fg_color="#2C3E57", command=self._render_quarantine,
        ).pack(side="right")
        ctk.CTkLabel(
            controls, text=self.t("quarantine_hint"), text_color=self.COLORS["muted"], anchor="e",
        ).pack(side="right", padx=14)
        self.quarantine_frame = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.quarantine_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 12))
        self._render_quarantine()

    def _render_quarantine(self) -> None:
        if not hasattr(self, "quarantine_frame"):
            return
        for widget in self.quarantine_frame.winfo_children():
            widget.destroy()
        items = Storage.list_quarantine()
        if not items:
            ctk.CTkLabel(
                self.quarantine_frame, text=self.t("quarantine_empty"), text_color=self.COLORS["muted"],
            ).pack(pady=32)
            return
        for item in items:
            original = str(item.metadata.get("path", "المسار الأصلي غير متاح"))
            score = item.metadata.get("score", "—")
            row = ctk.CTkFrame(self.quarantine_frame, fg_color="#16243A", corner_radius=10)
            row.pack(fill="x", padx=2, pady=5)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=f"{item.file_path.name}  •  درجة الفحص: {score}", anchor="e", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, padx=14, pady=(12, 2), sticky="e"
            )
            ctk.CTkLabel(row, text=f"{self.t('original_location')}: {original}", anchor="e", justify="right", wraplength=620, text_color=self.COLORS["muted"], font=ctk.CTkFont(size=12)).grid(
                row=1, column=0, padx=14, pady=(0, 12), sticky="ew"
            )
            actions = ctk.CTkFrame(row, fg_color="transparent")
            actions.grid(row=0, column=1, rowspan=2, padx=12, pady=10)
            ctk.CTkButton(actions, text=self.t("restore"), width=95, height=28, fg_color="#2C3E57", command=lambda i=item: self._restore_quarantined(i)).pack(pady=(0, 6))
            ctk.CTkButton(actions, text=self.t("permanent_delete"), width=95, height=28, fg_color=self.COLORS["danger"], command=lambda i=item: self._delete_quarantined(i)).pack()

    def _restore_quarantined(self, item: QuarantineItem) -> None:
        original_path = item.metadata.get("path")
        choice = messagebox.askyesnocancel(
            "استعادة ملف",
            "نعم: استعادة إلى المكان الأصلي.\nلا: اختيار مجلد آمن بنفسك.\nإلغاء: عدم إجراء أي تغيير.",
        )
        if choice is None:
            return
        destination: Optional[Path] = None
        if choice is False or not original_path:
            selected = filedialog.askdirectory(title="اختر مجلد استعادة آمن")
            if not selected:
                return
            destination = Path(selected)
        try:
            restored_to = Storage.restore_quarantine(item, destination)
            Storage.append_history({"kind": "استعادة ملف معزول", "at": datetime.now().isoformat(timespec="seconds"), "target": str(restored_to)})
            self._render_quarantine()
            messagebox.showinfo(APP_NAME, f"تمت الاستعادة إلى:\n{restored_to}")
        except (OSError, FileNotFoundError, FileExistsError, shutil.Error) as error:
            messagebox.showerror(APP_NAME, f"تعذرت الاستعادة؛ اختر مجلداً آخر إن كان الاسم موجوداً:\n{error}")

    def _delete_quarantined(self, item: QuarantineItem) -> None:
        first = messagebox.askyesno("تأكيد الحذف", f"هل تريد حذف الملف المعزول نهائياً؟\n\n{item.file_path.name}")
        if not first:
            return
        second = messagebox.askyesno("تأكيد أخير", "لن تتمكن من استعادة الملف بعد هذه الخطوة. هل تريد الحذف النهائي؟")
        if not second:
            return
        try:
            Storage.delete_quarantined(item)
            Storage.append_history({"kind": "حذف نهائي من العزل", "at": datetime.now().isoformat(timespec="seconds"), "target": item.file_path.name})
            self._render_quarantine()
        except OSError as error:
            messagebox.showerror(APP_NAME, f"تعذر الحذف النهائي:\n{error}")

    def _build_startup_page(self) -> None:
        self._section_title(self.t("startup"), self.t("startup_subtitle"))
        card = self._card(self.page_host)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(1, weight=1)
        controls = ctk.CTkFrame(card, fg_color="transparent")
        controls.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        ctk.CTkButton(controls, text=self.t("refresh"), width=120, fg_color="#2C3E57", command=self._render_startup).pack(side="right")
        ctk.CTkLabel(controls, text=self.t("startup_hint"), text_color=self.COLORS["muted"], anchor="e").pack(side="right", padx=14)
        self.startup_frame = ctk.CTkScrollableFrame(card, fg_color="transparent")
        self.startup_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 12))
        self._render_startup()

    def _render_startup(self) -> None:
        if not hasattr(self, "startup_frame"):
            return
        for widget in self.startup_frame.winfo_children():
            widget.destroy()
        entries = StartupManager.list_entries()
        disabled = StartupManager.list_disabled()
        if not entries and not disabled:
            ctk.CTkLabel(self.startup_frame, text=self.t("startup_empty"), text_color=self.COLORS["muted"]).pack(pady=28)
        for entry in entries:
            row = ctk.CTkFrame(self.startup_frame, fg_color="#16243A", corner_radius=10)
            row.pack(fill="x", padx=2, pady=5)
            row.grid_columnconfigure(0, weight=1)
            source = self.t("registry") if entry.source == "registry" else self.t("startup_folder")
            ctk.CTkLabel(row, text=f"{entry.name}  •  {source}", anchor="e", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=14, pady=(12, 2), sticky="e")
            ctk.CTkLabel(row, text=entry.command, anchor="e", justify="right", wraplength=620, text_color=self.COLORS["muted"], font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")
            ctk.CTkButton(row, text=self.t("startup_disable"), width=145, height=28, fg_color="#2C3E57", command=lambda e=entry: self._disable_startup(e)).grid(row=0, column=1, rowspan=2, padx=12, pady=12)
        if disabled:
            ctk.CTkLabel(self.startup_frame, text=self.t("disabled_before"), anchor="e", text_color=self.COLORS["warning"], font=ctk.CTkFont(weight="bold")).pack(fill="x", padx=10, pady=(18, 5))
        for record in disabled:
            row = ctk.CTkFrame(self.startup_frame, fg_color="#16243A", corner_radius=10)
            row.pack(fill="x", padx=2, pady=5)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=str(record.get("name", "برنامج")), anchor="e", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=14, pady=(12, 2), sticky="e")
            ctk.CTkLabel(row, text=f"تم التعطيل: {record.get('disabled_at', '')}", anchor="e", text_color=self.COLORS["muted"], font=ctk.CTkFont(size=12)).grid(row=1, column=0, padx=14, pady=(0, 12), sticky="e")
            ctk.CTkButton(row, text=self.t("restore"), width=115, height=28, fg_color=self.COLORS["accent"], command=lambda r=record: self._restore_startup(r)).grid(row=0, column=1, rowspan=2, padx=12, pady=12)

    def _disable_startup(self, entry: StartupEntry) -> None:
        if not messagebox.askyesno(APP_NAME, f"سيُمنع هذا البرنامج من العمل عند تشغيل Windows فقط، ولن يُحذف.\n\n{entry.name}\n\nهل تريد المتابعة؟"):
            return
        try:
            StartupManager.disable(entry)
            Storage.append_history({"kind": "تعطيل بدء التشغيل", "at": datetime.now().isoformat(timespec="seconds"), "target": entry.name})
            self._render_startup()
        except (OSError, FileNotFoundError, FileExistsError) as error:
            messagebox.showerror(APP_NAME, f"تعذر تعطيل برنامج بدء التشغيل:\n{error}")

    def _restore_startup(self, record: dict) -> None:
        if not messagebox.askyesno(APP_NAME, f"هل تريد إعادة تفعيل {record.get('name', 'هذا البرنامج')} عند بدء Windows؟"):
            return
        try:
            StartupManager.restore(record)
            Storage.append_history({"kind": "استعادة بدء التشغيل", "at": datetime.now().isoformat(timespec="seconds"), "target": record.get("name", "")})
            self._render_startup()
        except (OSError, FileNotFoundError, FileExistsError) as error:
            messagebox.showerror(APP_NAME, f"تعذرت الاستعادة:\n{error}")

    def _build_boost_page(self) -> None:
        self._section_title(self.t("boost"), self.t("boost_subtitle"))
        body = ctk.CTkFrame(self.page_host, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew")
        body.grid_columnconfigure(0, weight=1)
        info = self._card(body)
        info.grid(row=0, column=0, sticky="ew")
        info.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(info, text=self.t("boost_what"), anchor="e", font=ctk.CTkFont(size=19, weight="bold")).grid(
            row=0, column=0, padx=24, pady=(24, 10), sticky="e"
        )
        ctk.CTkLabel(
            info,
            text=self.t("boost_description"),
            justify="right", anchor="e", text_color=self.COLORS["muted"], font=ctk.CTkFont(size=14),
        ).grid(row=1, column=0, padx=24, pady=(0, 20), sticky="e")
        self.boost_button = ctk.CTkButton(
            info, text=self.t("boost_now"), width=205, height=46, corner_radius=11,
            fg_color=self.COLORS["accent"], hover_color=self.COLORS["accent_hover"], command=self._start_boost,
        )
        self.boost_button.grid(row=2, column=0, padx=24, pady=(0, 25), sticky="e")
        self.boost_status = ctk.CTkLabel(body, text=self.t("boost_idle"), text_color=self.COLORS["muted"], anchor="e")
        self.boost_status.grid(row=1, column=0, sticky="e", pady=14)

    def _start_boost(self) -> None:
        if self.busy:
            messagebox.showinfo(APP_NAME, "توجد عملية تعمل الآن. انتظر حتى تنتهي أو أوقف الفحص أولاً.")
            return
        if not messagebox.askyesno(APP_NAME, "سيُنظف البرنامج الملفات المؤقتة القديمة في حسابك فقط. هل تريد المتابعة؟"):
            return
        self.busy = True
        self.boost_button.configure(state="disabled", text="جارٍ التنظيف…")
        self.boost_status.configure(text="يتم فحص مجلد الملفات المؤقتة بحدود آمنة…")
        self._run_background("boost", self._safe_temp_cleanup)

    def _safe_temp_cleanup(self) -> None:
        """تنظيف محدود لمجلد TEMP الخاص بالمستخدم، لا يشمل القرص أو مجلد النظام."""
        # نقتصر على TEMP الخاص بالحساب الحالي، ولا نستخدم TEMP النظام حتى لو عُدّلت البيئة.
        local_app_data = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        root = local_app_data / "Temp"
        if not root.is_dir():
            self.worker_queue.put(("boost_done", 0, 0, 0))
            return
        cutoff = time.time() - (12 * 60 * 60)
        removed_files = 0
        freed_bytes = 0
        checked = 0
        started = time.monotonic()
        stack = [root]
        while stack and removed_files < 1_500 and (time.monotonic() - started) < 20:
            current = stack.pop()
            try:
                with os.scandir(current) as entries:
                    for entry in entries:
                        if removed_files >= 1_500 or (time.monotonic() - started) >= 20:
                            break
                        try:
                            if entry.is_symlink():
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                stack.append(Path(entry.path))
                                continue
                            if not entry.is_file(follow_symlinks=False):
                                continue
                            checked += 1
                            stat = entry.stat(follow_symlinks=False)
                            if stat.st_mtime > cutoff:
                                continue
                            size = stat.st_size
                            os.remove(entry.path)
                            removed_files += 1
                            freed_bytes += size
                        except (OSError, PermissionError):
                            # الملف المشغول أو المحمي يترك كما هو، فلا نؤثر في أي برنامج.
                            continue
            except (OSError, PermissionError):
                continue
        event = {
            "kind": "تنظيف مؤقت آمن", "at": datetime.now().isoformat(timespec="seconds"),
            "files_removed": removed_files, "freed_bytes": freed_bytes, "checked": checked,
        }
        try:
            Storage.append_history(event)
        except OSError:
            pass
        self.worker_queue.put(("boost_done", removed_files, freed_bytes, checked))

    def _build_history_page(self) -> None:
        self._section_title(self.t("history"), self.t("history_subtitle"))
        card = self._card(self.page_host)
        card.grid(row=1, column=0, sticky="nsew")
        card.grid_columnconfigure(0, weight=1)
        card.grid_rowconfigure(0, weight=1)
        scroll = ctk.CTkScrollableFrame(card, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        history = list(reversed(Storage.read_history()))
        if not history:
            ctk.CTkLabel(scroll, text=self.t("history_empty"), text_color=self.COLORS["muted"]).pack(pady=30)
            return
        for item in history:
            kind = item.get("kind", "عملية")
            when = item.get("at", "")
            text_parts = [f"{kind}  •  {when}"]
            if "target" in item:
                text_parts.append(str(item["target"]))
            if "files" in item:
                text_parts.append(f"فُحص: {item['files']} | نتائج: {item.get('findings', 0)}")
            if "freed_bytes" in item:
                text_parts.append(f"تمت إزالة: {item.get('files_removed', 0)} ملف | استرجاع {human_size(item['freed_bytes'])}")
            row = ctk.CTkLabel(scroll, text="\n".join(text_parts), justify="right", anchor="e", fg_color="#16243A", corner_radius=10, padx=15, pady=12)
            row.pack(fill="x", pady=4)

    def _run_background(self, task: str, worker: Callable[[], None]) -> None:
        def wrapped() -> None:
            try:
                worker()
            except Exception as error:  # حاجز أخطاء لمنع توقف الواجهة عند مشكلة في الملفات.
                self.worker_queue.put(("error", task, str(error)))
        threading.Thread(target=wrapped, name=f"nimbleguard-{task}", daemon=True).start()

    def _process_worker_events(self) -> None:
        try:
            while True:
                event = self.worker_queue.get_nowait()
                kind = event[0]
                if kind == "progress" and self.active_page == "scan" and hasattr(self, "scan_progress"):
                    _, current, total, name = event
                    # في المجلدات لا نعرف العدد مسبقاً؛ الشريط يوضح تقدماً محدوداً لا وعداً زائفاً.
                    self.scan_progress.set(min(0.97, current / max(total, 1)))
                    self.scan_status.configure(text=f"فُحص {current} ملف… {name}")
                elif kind == "result":
                    self.results.append(event[1])
                    if self.active_page == "scan":
                        self._render_results()
                elif kind == "scan_done":
                    _, found, inspected, skipped, cancelled = event
                    self.results = found
                    self.busy = False
                    if self.active_page == "scan" and hasattr(self, "scan_progress"):
                        self.scan_progress.set(1 if not cancelled else 0)
                        self.scan_status.configure(
                            text=("تم إيقاف الفحص" if cancelled else "اكتمل الفحص") + f" — فُحص {inspected} ملف، نتائج: {len(found)}، متجاوز: {skipped}"
                        )
                        self.scan_file_button.configure(state="normal")
                        self.scan_folder_button.configure(state="normal")
                        self.scan_quick_button.configure(state="normal")
                        self.cancel_button.configure(state="disabled")
                        self._render_results()
                elif kind == "boost_done":
                    _, removed, freed, checked = event
                    self.busy = False
                    if self.active_page == "boost" and hasattr(self, "boost_button"):
                        self.boost_button.configure(state="normal", text="ϟ خفّف الجهاز الآن")
                        self.boost_status.configure(
                            text=f"اكتمل بأمان: أزيل {removed} ملفاً واستُرجع {human_size(freed)} (فُحص {checked} ملفاً)."
                        )
                elif kind == "signature_done":
                    _, file_path, detail = event
                    self.signature_status[file_path] = detail
                    if self.active_page == "scan":
                        self._render_results()
                elif kind == "gpu_info":
                    self.gpu_name = event[1]
                    if self.active_page == "dashboard" and hasattr(self, "gpu_caption") and self.gpu_caption.winfo_exists():
                        self.gpu_caption.configure(text=self.gpu_name)
                elif kind == "defender_status":
                    _, enabled, real_time, signature_date = event
                    self.defender_info = {
                        "enabled": enabled,
                        "real_time": real_time,
                        "signature_date": signature_date,
                        "label": self._format_defender_status(enabled, real_time, signature_date),
                    }
                    self._update_defender_card()
                elif kind == "defender_scan_done":
                    _, scan_type, succeeded, detail = event
                    self.defender_scan_running = False
                    self._update_defender_card()
                    if succeeded:
                        title = "فحص النظام اكتمل" if scan_type == "FullScan" else "الفحص السريع اكتمل"
                        messagebox.showinfo(APP_NAME, f"{title} عبر Microsoft Defender.\n\n{detail}")
                        self._run_background("defender_status", self._load_defender_status)
                    else:
                        messagebox.showerror(APP_NAME, f"تعذر تشغيل فحص Microsoft Defender:\n{detail}")
                elif kind == "defender_update_done":
                    _, succeeded, detail = event
                    self._update_defender_card()
                    if succeeded:
                        messagebox.showinfo(APP_NAME, "تم طلب تحديث قاعدة Microsoft Defender بنجاح.\n" + detail)
                        self._run_background("defender_status", self._load_defender_status)
                    else:
                        messagebox.showerror(APP_NAME, f"تعذر تحديث قاعدة Microsoft Defender:\n{detail}")
                elif kind == "monitor_alert":
                    verdict = event[1]
                    try:
                        Storage.append_history({
                            "kind": "تنبيه حماية التنزيلات", "at": datetime.now().isoformat(timespec="seconds"),
                            "target": verdict.path, "findings": 1,
                        })
                    except OSError:
                        pass
                    messagebox.showwarning(
                        APP_NAME,
                        "اكتشفت حماية التنزيلات ملفاً يحتاج مراجعة:\n\n"
                        f"{verdict.path}\n\n{verdict.label} — {verdict.score}/100\n"
                        "افتح الفحص الذكي لمراجعته أو عزله اختيارياً.",
                    )
                elif kind == "error":
                    _, task, detail = event
                    if task == "scan":
                        self.busy = False
                    if task == "boost":
                        self.busy = False
                    if task == "scan" and self.active_page == "scan" and hasattr(self, "scan_file_button"):
                        self.scan_file_button.configure(state="normal")
                        self.scan_folder_button.configure(state="normal")
                        self.scan_quick_button.configure(state="normal")
                        self.cancel_button.configure(state="disabled")
                    if task == "boost" and self.active_page == "boost" and hasattr(self, "boost_button"):
                        self.boost_button.configure(state="normal", text="ϟ خفّف الجهاز الآن")
                    messagebox.showerror(APP_NAME, f"تعذر إكمال عملية {task}:\n{detail}")
        except queue.Empty:
            pass
        self.after(250, self._process_worker_events)

    def _set_protection(self, enabled: bool) -> None:
        """تفعيل مراقبة خفيفة ومحددة لتنزيلات المستخدم، لا مضاد فيروسات دائم."""
        if self.protection_enabled == enabled:
            return
        self.protection_enabled = enabled
        self.monitor_generation += 1
        if self.protection_enabled:
            self.download_snapshot = self._download_files_snapshot()
            self._schedule_download_monitor(self.monitor_generation)
        self._update_protection_badge()
        self._update_protection_card()
        try:
            Storage.append_history({
                "kind": "تشغيل حماية التنزيلات" if self.protection_enabled else "إيقاف حماية التنزيلات",
                "at": datetime.now().isoformat(timespec="seconds"),
            })
        except OSError:
            pass

    def _update_protection_card(self) -> None:
        if self.active_page != "dashboard" or not hasattr(self, "protection_status_label") or not self.protection_status_label.winfo_exists():
            return
        if self.protection_enabled:
            state = "مفعلة: تفحص الملفات التنفيذية الجديدة في Downloads كل 30 ثانية."
        else:
            state = "متوقفة: لا توجد مراقبة للتنزيلات في الخلفية."
        self.protection_status_label.configure(text=state, text_color=self.COLORS["accent"] if self.protection_enabled else self.COLORS["muted"])
        self.protection_on_button.configure(fg_color=self.COLORS["accent"] if self.protection_enabled else "#2C8E68")
        self.protection_off_button.configure(fg_color="#C24141" if not self.protection_enabled else "#34445B")

    @staticmethod
    def _format_defender_status(enabled: bool, real_time: bool, signature_date: str) -> str:
        if not enabled:
            return "Microsoft Defender غير نشط أو أن مضاداً آخر يدير الحماية."
        real_time_text = "مفعلة" if real_time else "متوقفة"
        suffix = f" • آخر تحديث: {signature_date}" if signature_date else ""
        return f"Defender نشط • الحماية اللحظية: {real_time_text}{suffix}"

    def _update_defender_card(self) -> None:
        if self.active_page != "dashboard" or not hasattr(self, "defender_status_label") or not self.defender_status_label.winfo_exists():
            return
        label = self.defender_info.get("label", self.t("defender_loading"))
        color = self.COLORS["accent"] if self.defender_info.get("enabled") else self.COLORS["warning"]
        self.defender_status_label.configure(text=label, text_color=color)
        state = "disabled" if self.defender_scan_running else "normal"
        self.defender_quick_button.configure(state=state)
        self.defender_full_button.configure(state=state)
        self.defender_update_button.configure(state=state)

    def _load_defender_status(self) -> None:
        """قراءة حالة Defender وتاريخ قواعده من واجهة Windows الرسمية، مرة واحدة فقط."""
        script = (
            "$s=Get-MpComputerStatus -ErrorAction Stop;"
            "[PSCustomObject]@{Enabled=$s.AntivirusEnabled;RealTime=$s.RealTimeProtectionEnabled;"
            "Signature=if($s.AntivirusSignatureLastUpdated){$s.AntivirusSignatureLastUpdated.ToString('yyyy-MM-dd HH:mm')}else{''}}|ConvertTo-Json -Compress"
        )
        enabled = False
        real_time = False
        signature_date = ""
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=12, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout.strip())
                enabled = bool(data.get("Enabled"))
                real_time = bool(data.get("RealTime"))
                signature_date = str(data.get("Signature") or "")
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            pass
        self.worker_queue.put(("defender_status", enabled, real_time, signature_date))

    def _start_defender_scan(self, scan_type: str) -> None:
        """بدء فحص Microsoft Defender الحقيقي بعد موافقة واضحة، لأن الفحص الكامل قد يطول."""
        if self.defender_scan_running:
            return
        if not self.defender_info.get("enabled"):
            messagebox.showwarning(APP_NAME, "Microsoft Defender غير نشط حالياً، لذا لا يمكن بدء الفحص من NimbleGuard.")
            return
        if scan_type == "FullScan":
            approved = messagebox.askyesno(
                "فحص كامل للنظام",
                "سيستخدم Microsoft Defender لفحص النظام كاملاً. قد يستغرق وقتاً ويزيد استخدام القرص والمعالج. هل تريد البدء؟",
            )
            if not approved:
                return
        self.defender_scan_running = True
        self._update_defender_card()
        self._run_background("defender_scan", lambda: self._defender_scan_worker(scan_type))

    def _defender_scan_worker(self, scan_type: str) -> None:
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", f"Start-MpScan -ScanType {scan_type}"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            )
            if result.returncode == 0:
                detail = "راجع Windows Security إذا ظهر تنبيه أو ملف معزول بواسطة Defender."
                self.worker_queue.put(("defender_scan_done", scan_type, True, detail))
            else:
                self.worker_queue.put(("defender_scan_done", scan_type, False, result.stderr.strip() or "أعاد Defender رمز خطأ."))
        except (OSError, subprocess.SubprocessError) as error:
            self.worker_queue.put(("defender_scan_done", scan_type, False, str(error)))

    def _update_defender_signatures(self) -> None:
        if self.defender_scan_running:
            return
        if not self.defender_info.get("enabled"):
            messagebox.showwarning(APP_NAME, "Microsoft Defender غير نشط حالياً.")
            return
        if not messagebox.askyesno(APP_NAME, "سيطلب Defender تحديث قواعد الفيروسات من خدمة Microsoft. هل تريد المتابعة؟"):
            return
        self.defender_scan_running = True
        self._update_defender_card()
        self._run_background("defender_update", self._defender_update_worker)

    def _defender_update_worker(self) -> None:
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Update-MpSignature"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180, check=False,
            )
            self.defender_scan_running = False
            if result.returncode == 0:
                self.worker_queue.put(("defender_update_done", True, "سيتم تحديث الحالة تلقائياً."))
            else:
                self.worker_queue.put(("defender_update_done", False, result.stderr.strip() or "تعذر الوصول إلى خدمة التحديث."))
        except (OSError, subprocess.SubprocessError) as error:
            self.defender_scan_running = False
            self.worker_queue.put(("defender_update_done", False, str(error)))

    @staticmethod
    def _download_files_snapshot() -> dict[str, tuple[float, int]]:
        """لقطة للملفات التنفيذية المباشرة في Downloads؛ لا استكشاف متكرر لكل القرص."""
        snapshot: dict[str, tuple[float, int]] = {}
        downloads = Path.home() / "Downloads"
        try:
            for child in downloads.iterdir():
                if not child.is_file() or child.is_symlink() or child.suffix.lower() not in RISKY_EXTENSIONS:
                    continue
                stat = child.stat()
                snapshot[str(child)] = (stat.st_mtime, stat.st_size)
        except OSError:
            pass
        return snapshot

    def _schedule_download_monitor(self, generation: int) -> None:
        self.after(30_000, lambda: self._monitor_downloads(generation))

    def _monitor_downloads(self, generation: int) -> None:
        if not self.protection_enabled or generation != self.monitor_generation:
            return
        current = self._download_files_snapshot()
        changed = [Path(path) for path, fingerprint in current.items() if self.download_snapshot.get(path) != fingerprint]
        self.download_snapshot = current
        if changed:
            self._run_background("monitor", lambda: self._monitor_new_downloads(changed))
        self._schedule_download_monitor(generation)

    def _monitor_new_downloads(self, paths: list[Path]) -> None:
        cancel = threading.Event()
        for file_path in paths[:20]:  # حد دفاعي إن وصل عدد كبير من الملفات في وقت واحد.
            verdict = RiskEngine.inspect(file_path, cancel)
            if verdict is not None and verdict.score >= 30:
                self.worker_queue.put(("monitor_alert", verdict))

    def _load_gpu_info(self) -> None:
        """قراءة اسم بطاقة العرض مرة واحدة فقط من Windows؛ لا يوجد قياس GPU موحد في psutil."""
        script = "Get-CimInstance Win32_VideoController | Select-Object -First 1 -ExpandProperty Name"
        name = "كرت الشاشة غير متاح"
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8, check=False,
            )
            if result.stdout.strip():
                name = result.stdout.strip().splitlines()[0]
        except (OSError, subprocess.SubprocessError):
            pass
        self.worker_queue.put(("gpu_info", name))

    def _refresh_metrics(self) -> None:
        """تحديث متباعد جداً لبيانات النظام كي لا يصبح البرنامج نفسه عبئاً."""
        try:
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage(Path.home().anchor or "C:\\")
            if hasattr(self, "cpu_value") and self.active_page == "dashboard":
                self.cpu_value.configure(text=f"{cpu:.0f}%")
                self.cpu_bar.set(max(0, min(1, cpu / 100)))
                self.memory_value.configure(text=f"{memory.percent:.0f}%")
                self.memory_bar.set(max(0, min(1, memory.percent / 100)))
                self.gpu_value.configure(text="GPU")
                self.gpu_bar.set(0.15)
                self.gpu_caption.configure(text=self.gpu_name)
                self.disk_value.configure(text=f"{human_size(disk.free)}")
                self.disk_bar.set(max(0, min(1, disk.used / disk.total)))
            if hasattr(self, "top_processes_label") and self.active_page == "dashboard" and self.top_processes_label.winfo_exists():
                self.top_processes_label.configure(text=self._top_process_summary())
        except (OSError, ValueError):
            pass
        self.after(5_000, self._refresh_metrics)

    @staticmethod
    def _top_process_summary() -> str:
        """عرض ثلاثة تطبيقات تستهلك الذاكرة فقط؛ لا نوقف أي عملية ولا نراقب باستمرار."""
        samples: list[tuple[float, str]] = []
        for process in psutil.process_iter(["name", "memory_percent"]):
            try:
                memory = float(process.info.get("memory_percent") or 0)
                name = str(process.info.get("name") or "عملية غير معروفة")
                if memory > 0:
                    samples.append((memory, name))
            except (psutil.Error, OSError, ValueError):
                continue
        if not samples:
            return "لا توجد بيانات عمليات متاحة الآن."
        top_three = sorted(samples, reverse=True)[:3]
        return "   |   ".join(f"{name}: {memory:.1f}% RAM" for memory, name in top_three)


if __name__ == "__main__":
    Storage.ensure()
    app = NimbleGuardApp()
    app.mainloop()
