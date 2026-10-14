"""Tiny two-language string catalogue (Thai first, English fallback).

Kept free of Qt so it can be imported by tests and tools. `t()` returns the
active language's text, falling back to English and finally to the key itself,
which makes a missing translation obvious instead of raising.
"""

from __future__ import annotations

DEFAULT_LANGUAGE = "th"
LANGUAGES = (("th", "ไทย"), ("en", "English"))

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app.title": "HeadSize Studio",
        "app.tagline": "Resize the head of anyone in a photo",
        "app.version": "Version {version}",
        # menus
        "menu.file": "&File",
        "menu.edit": "&Edit",
        "menu.view": "&View",
        "menu.tools": "&Tools",
        "menu.help": "&Help",
        # actions
        "action.open": "Open image…",
        "action.recent": "Recent files",
        "action.save": "Save",
        "action.save_as": "Save as…",
        "action.quit": "Quit",
        "action.undo": "Undo",
        "action.redo": "Redo",
        "action.reset_edits": "Reset all edits",
        "action.auto_detect": "Detect faces",
        "action.add_head": "Add head region",
        "action.remove_head": "Delete head region",
        "action.clear_regions": "Delete all head regions",
        "action.apply_all": "Apply size to all",
        "action.duplicate": "Duplicate head region",
        "action.zoom_in": "Zoom in",
        "action.zoom_out": "Zoom out",
        "action.zoom_fit": "Fit to window",
        "action.zoom_reset": "Actual size (100%)",
        "action.toggle_overlay": "Show influence zone",
        "action.compare": "Compare with original",
        "action.split": "Split view",
        "action.check_updates": "Check for updates…",
        "action.settings": "Settings…",
        "action.shortcuts": "Keyboard shortcuts",
        "action.docs": "Open documentation",
        "action.about": "About HeadSize Studio",
        "action.theme": "Toggle dark / light theme",
        "action.language": "Language / ภาษา",
        "action.download_model": "Download face model",
        "action.export": "Export…",
        # cards
        "card.image": "Image",
        "card.faces": "Heads in this photo",
        "card.size": "Head size",
        "card.region": "Influence zone",
        "card.view": "View & output",
        "card.updates": "Updates",
        # image card
        "button.open": "Open an image",
        "button.save": "Save a copy",
        "button.reset": "Start over",
        "hint.drop": "Drag an image here or press Ctrl+O",
        "empty.title": "No image yet",
        "empty.body": "Open a photo, or drop one onto this window.\nThe head is detected automatically.",
        "label.no_file": "No file loaded",
        "label.size": "{width} × {height} px",
        "label.size_key": "Pixels",
        "label.faces_key": "Heads",
        # faces card
        "button.detect": "Detect faces",
        "button.detecting": "Detecting…",
        "button.add_manual": "Add a head by hand",
        "button.apply_all": "Use this size for every head",
        "faces.none": "No head regions yet.",
        "faces.count": "{count} head region(s)",
        "faces.detected": "Found {count} face(s)",
        "faces.not_found": "No face found — add a head region by hand or draw one.",
        "region.title": "Head {index}",
        # size card
        "scale.value": "{value:.2f}×",
        "scale.smaller": "Smaller",
        "scale.bigger": "Bigger",
        "scale.reset": "Back to 100%",
        "scale.hint": "1.00× leaves the head untouched",
        # region card
        "region.feather": "Edge softness",
        "region.width": "Zone width",
        "region.height": "Zone height",
        "region.offset_y": "Zone height position",
        "region.rotation": "Tilt",
        "region.show": "Show the influence zone",
        "region.autofit": "Fit the zone to the face",
        # view card
        "view.quality": "Render quality",
        "view.quality.fast": "Fast",
        "view.quality.balanced": "Balanced",
        "view.quality.high": "High",
        "view.compare": "Compare",
        "view.type.original": "Original",
        "view.type.result": "Result",
        "view.type.split": "Split",
        "view.theme": "Theme",
        "view.language": "Language",
        "view.keep_metadata": "Keep EXIF / ICC / DPI when saving",
        # updates card
        "update.check": "Check now",
        "update.auto": "Check automatically at start-up",
        "update.channel": "Channel",
        "update.channel.stable": "Stable",
        "update.channel.beta": "Beta",
        "update.repo": "Repository",
        "update.up_to_date": "You are up to date ({version}).",
        "update.available": "Version {version} is available.",
        "update.downloading": "Downloading… {percent}%",
        "update.installing": "Installing… the app will restart.",
        "update.failed": "Update failed: {message}",
        "update.disabled": "Auto-update is not configured for this build.",
        "update.open_page": "Open release page",
        "update.skip": "Skip this version",
        "update.now": "Update now",
        "update.later": "Later",
        "update.checking": "Checking for updates…",
        # status bar
        "status.ready": "Ready",
        "status.loading": "Loading {name}…",
        "status.loaded": "Loaded {name} — {width} × {height} px",
        "status.detecting": "Looking for faces…",
        "status.saved": "Saved to {path}",
        "status.zoomed": "Zoom {percent}%",
        "status.edited": "Edited",
        "status.no_image": "No image",
        "status.regions": "{count} head region(s)",
        "status.render": "Rendering…",
        "status.cursor": "x {x}, y {y}",
        # dialogs
        "dialog.open_title": "Open an image",
        "dialog.save_title": "Save the edited image",
        "dialog.export_title": "Export options",
        "dialog.overwrite_title": "Overwrite?",
        "dialog.overwrite_body": "{name} already exists. Replace it?",
        "dialog.error_title": "Something went wrong",
        "dialog.open_error": "The image could not be opened.\n\n{message}",
        "dialog.save_error": "The image could not be saved.\n\n{message}",
        "dialog.detect_error": "Face detection is unavailable.\n\n{message}",
        "dialog.model_title": "Face model missing",
        "dialog.model_body": (
            "The YuNet face model could not be found. Download it now "
            "(about 225 kB) or place head regions by hand."
        ),
        "dialog.model_download": "Download",
        "dialog.model_later": "Not now",
        "dialog.unsaved_title": "Unsaved edits",
        "dialog.unsaved_body": "Your head-size edits are not saved yet.",
        "dialog.discard": "Discard",
        "dialog.save_and_close": "Save and close",
        "dialog.keep": "Keep editing",
        "dialog.close_title": "Close HeadSize Studio?",
        "dialog.close_body": "Any unsaved edits will be lost.",
        "dialog.model_done": "Face model downloaded.",
        "dialog.model_failed": "Could not download the face model.\n\n{message}",
        # about
        "about.body": (
            "<h2>HeadSize Studio {version}</h2>"
            "<p>{tagline}</p>"
            "<p>Detects faces with the YuNet DNN detector and grows or shrinks the "
            "head with a smooth elliptical warp, so the result stays photographic "
            "instead of looking cut out.</p>"
            "<p>Built with PyQt6, OpenCV and NumPy. Face model © Shiqi Yu (MIT).</p>"
        ),
        "shortcuts.title": "Keyboard shortcuts",
        "zoom.percent": "{percent}%",
        "unit.px": "px",
    },
    "th": {
        "app.title": "HeadSize Studio",
        "app.tagline": "ปรับขนาดศีรษะของคนในรูปให้ใหญ่ขึ้นหรือเล็กลงได้ในไม่กี่วินาที",
        "app.version": "เวอร์ชัน {version}",
        "menu.file": "ไฟล์",
        "menu.edit": "แก้ไข",
        "menu.view": "มุมมอง",
        "menu.tools": "เครื่องมือ",
        "menu.help": "ช่วยเหลือ",
        "action.open": "เปิดรูปภาพ…",
        "action.recent": "ไฟล์ล่าสุด",
        "action.save": "บันทึก",
        "action.save_as": "บันทึกเป็น…",
        "action.quit": "ออกจากโปรแกรม",
        "action.undo": "ย้อนกลับ",
        "action.redo": "ทำซ้ำ",
        "action.reset_edits": "ล้างการแก้ไขทั้งหมด",
        "action.auto_detect": "ตรวจจับใบหน้า",
        "action.add_head": "เพิ่มโซนศีรษะ",
        "action.remove_head": "ลบโซนศีรษะ",
        "action.clear_regions": "ลบโซนศีรษะทั้งหมด",
        "action.apply_all": "ใช้ขนาดนี้กับทุกศีรษะ",
        "action.duplicate": "ทำสำเนาโซนศีรษะ",
        "action.zoom_in": "ขยาย",
        "action.zoom_out": "ย่อ",
        "action.zoom_fit": "พอดีหน้าต่าง",
        "action.zoom_reset": "ขนาดจริง (100%)",
        "action.toggle_overlay": "แสดงเส้นขอบโซน",
        "action.compare": "เทียบกับต้นฉบับ",
        "action.split": "มุมมองแบ่งครึ่ง",
        "action.check_updates": "ตรวจหาอัปเดต…",
        "action.settings": "ตั้งค่า…",
        "action.shortcuts": "คีย์ลัด",
        "action.docs": "เปิดเอกสารประกอบ",
        "action.about": "เกี่ยวกับ HeadSize Studio",
        "action.theme": "สลับธีมมืด / สว่าง",
        "action.language": "Language / ภาษา",
        "action.download_model": "ดาวน์โหลดโมเดลตรวจจับใบหน้า",
        "action.export": "ส่งออก…",
        "card.image": "รูปภาพ",
        "card.faces": "ศีรษะในรูปนี้",
        "card.size": "ขนาดศีรษะ",
        "card.region": "โซนที่ปรับ",
        "card.view": "มุมมองและผลลัพธ์",
        "card.updates": "อัปเดต",
        "button.open": "เปิดรูปภาพ",
        "button.save": "บันทึกสำเนา",
        "button.reset": "เริ่มใหม่",
        "hint.drop": "ลากรูปมาวางที่นี่ หรือกด Ctrl+O",
        "empty.title": "ยังไม่มีรูป",
        "empty.body": "เปิดรูปภาพ หรือลากไฟล์มาวางในหน้าต่างนี้\nโปรแกรมจะตรวจจับศีรษะให้อัตโนมัติ",
        "label.no_file": "ยังไม่ได้เปิดไฟล์",
        "label.size": "{width} × {height} พิกเซล",
        "label.size_key": "ขนาด",
        "label.faces_key": "จำนวน",
        "button.detect": "ตรวจจับใบหน้า",
        "button.detecting": "กำลังตรวจจับ…",
        "button.add_manual": "เพิ่มโซนศีรษะเอง",
        "button.apply_all": "ใช้ขนาดนี้กับทุกศีรษะ",
        "faces.none": "ยังไม่มีโซนศีรษะ",
        "faces.count": "มีโซนศีรษะ {count} จุด",
        "faces.detected": "พบใบหน้า {count} ใบ",
        "faces.not_found": "ไม่พบใบหน้า — เพิ่มโซนศีรษะเองหรือลากวางในภาพได้",
        "region.title": "ศีรษะที่ {index}",
        "scale.value": "{value:.2f}×",
        "scale.smaller": "เล็กลง",
        "scale.bigger": "ใหญ่ขึ้น",
        "scale.reset": "กลับไป 100%",
        "scale.hint": "1.00× คือขนาดเดิมไม่เปลี่ยนแปลง",
        "region.feather": "ความนุ่มของขอบ",
        "region.width": "ความกว้างโซน",
        "region.height": "ความสูงโซน",
        "region.offset_y": "ตำแหน่งแนวตั้งของโซน",
        "region.rotation": "เอียง",
        "region.show": "แสดงโซนที่ปรับ",
        "region.autofit": "ปรับโซนให้พอดีใบหน้า",
        "view.quality": "คุณภาพการประมวลผล",
        "view.quality.fast": "เร็ว",
        "view.quality.balanced": "สมดุล",
        "view.quality.high": "สูง",
        "view.compare": "เปรียบเทียบ",
        "view.type.original": "ต้นฉบับ",
        "view.type.result": "ผลลัพธ์",
        "view.type.split": "แบ่งครึ่ง",
        "view.theme": "ธีม",
        "view.language": "ภาษา",
        "view.keep_metadata": "เก็บ EXIF / ICC / DPI ตอนบันทึก",
        "update.check": "ตรวจสอบเดี๋ยวนี้",
        "update.auto": "ตรวจอัตโนมัติเมื่อเปิดโปรแกรม",
        "update.channel": "ช่องทาง",
        "update.channel.stable": "เสถียร",
        "update.channel.beta": "เบต้า",
        "update.repo": "ที่เก็บโค้ด",
        "update.up_to_date": "เป็นเวอร์ชันล่าสุดแล้ว ({version})",
        "update.available": "มีเวอร์ชันใหม่ {version}",
        "update.downloading": "กำลังดาวน์โหลด… {percent}%",
        "update.installing": "กำลังติดตั้ง… โปรแกรมจะรีสตาร์ทเอง",
        "update.failed": "อัปเดตไม่สำเร็จ: {message}",
        "update.disabled": "บิลด์นี้ยังไม่ได้ตั้งค่าอัปเดตอัตโนมัติ",
        "update.open_page": "เปิดหน้า Release",
        "update.skip": "ข้ามเวอร์ชันนี้",
        "update.now": "อัปเดตเลย",
        "update.later": "ไว้ทีหลัง",
        "update.checking": "กำลังตรวจหาอัปเดต…",
        "status.ready": "พร้อมใช้งาน",
        "status.loading": "กำลังเปิด {name}…",
        "status.loaded": "เปิด {name} — {width} × {height} พิกเซล",
        "status.detecting": "กำลังค้นหาใบหน้า…",
        "status.saved": "บันทึกไว้ที่ {path}",
        "status.zoomed": "ซูม {percent}%",
        "status.edited": "แก้ไขแล้ว",
        "status.no_image": "ไม่มีรูป",
        "status.regions": "โซนศีรษะ {count} จุด",
        "status.render": "กำลังประมวลผล…",
        "status.cursor": "x {x}, y {y}",
        "dialog.open_title": "เปิดรูปภาพ",
        "dialog.save_title": "บันทึกรูปที่แก้ไข",
        "dialog.export_title": "ตัวเลือกการส่งออก",
        "dialog.overwrite_title": "เขียนทับไฟล์เดิม?",
        "dialog.overwrite_body": "มีไฟล์ {name} อยู่แล้ว ต้องการเขียนทับหรือไม่",
        "dialog.error_title": "เกิดข้อผิดพลาด",
        "dialog.open_error": "ไม่สามารถเปิดรูปภาพนี้ได้\n\n{message}",
        "dialog.save_error": "ไม่สามารถบันทึกรูปภาพได้\n\n{message}",
        "dialog.detect_error": "ไม่สามารถตรวจจับใบหน้าได้\n\n{message}",
        "dialog.model_title": "ไม่พบโมเดลตรวจจับใบหน้า",
        "dialog.model_body": (
            "ไม่พบไฟล์โมเดล YuNet ต้องการดาวน์โหลดตอนนี้หรือไม่ "
            "(ประมาณ 225 kB) หรือจะเพิ่มโซนศีรษะเองก็ได้"
        ),
        "dialog.model_download": "ดาวน์โหลด",
        "dialog.model_later": "ไว้ก่อน",
        "dialog.unsaved_title": "ยังไม่ได้บันทึก",
        "dialog.unsaved_body": "การปรับขนาดศีรษะยังไม่ได้บันทึก",
        "dialog.discard": "ไม่บันทึก",
        "dialog.save_and_close": "บันทึกแล้วปิด",
        "dialog.keep": "แก้ไขต่อ",
        "dialog.close_title": "ปิด HeadSize Studio?",
        "dialog.close_body": "การแก้ไขที่ยังไม่บันทึกจะสูญหาย",
        "dialog.model_done": "ดาวน์โหลดโมเดลเรียบร้อยแล้ว",
        "dialog.model_failed": "ดาวน์โหลดโมเดลไม่สำเร็จ\n\n{message}",
        "about.body": (
            "<h2>HeadSize Studio {version}</h2>"
            "<p>{tagline}</p>"
            "<p>ตรวจจับใบหน้าด้วยโมเดล YuNet แล้วย่อ/ขยายศีรษะด้วยเทคนิค "
            "elliptical warp ที่ขอบนุ่มนวล ผลลัพธ์จึงดูเป็นภาพถ่ายจริง "
            "ไม่ใช่การตัดแปะ</p>"
            "<p>สร้างด้วย PyQt6, OpenCV และ NumPy · โมเดลใบหน้า © Shiqi Yu (MIT)</p>"
        ),
        "shortcuts.title": "คีย์ลัด",
        "zoom.percent": "{percent}%",
        "unit.px": "พิกเซล",
    },
}


class Translator:
    """Holds the active language and formats string templates."""

    def __init__(self, language: str = DEFAULT_LANGUAGE) -> None:
        self.language = language if language in STRINGS else DEFAULT_LANGUAGE

    def set_language(self, language: str) -> None:
        if language in STRINGS:
            self.language = language

    def t(self, key: str, **params) -> str:
        text = STRINGS.get(self.language, {}).get(key)
        if text is None:
            text = STRINGS["en"].get(key, key)
        if params:
            try:
                return text.format(**params)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    __call__ = t


#: Process-wide translator used by the UI.
translator = Translator()


def t(key: str, **params) -> str:
    return translator.t(key, **params)


def set_language(language: str) -> None:
    translator.set_language(language)


def current_language() -> str:
    return translator.language


def available_languages() -> tuple[tuple[str, str], ...]:
    return LANGUAGES


def missing_keys(language: str = "th") -> list[str]:
    """Keys present in English but absent from ``language`` (used by tests)."""
    english = set(STRINGS["en"])
    return sorted(english - set(STRINGS.get(language, {})))


__all__ = [
    "DEFAULT_LANGUAGE",
    "LANGUAGES",
    "STRINGS",
    "Translator",
    "available_languages",
    "current_language",
    "missing_keys",
    "set_language",
    "t",
    "translator",
]
