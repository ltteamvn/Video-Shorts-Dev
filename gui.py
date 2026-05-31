#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI Shorts Generator — PyQt5 Desktop GUI
Hỗ trợ Claude (Anthropic) và Gemini (Google) để tạo storyboard.
Nhập API key, dán URL bài viết / repo GitHub, bấm Generate → Render → (tùy chọn) Voice-over
"""

import os, sys, json, re, shutil, subprocess, threading, datetime, pathlib, textwrap
import requests
from bs4 import BeautifulSoup

# Provider constants
PROVIDER_CLAUDE  = "Claude (Anthropic)"
PROVIDER_GEMINI  = "Gemini (Google)"

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QPlainTextEdit, QPushButton,
    QComboBox, QCheckBox, QFileDialog, QGroupBox, QSplitter,
    QProgressBar, QMessageBox, QSizePolicy, QScrollArea, QFrame,
    QSpacerItem, QRadioButton, QButtonGroup
)
from PyQt5.QtCore import Qt, QThread, QObject, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette, QTextCursor, QIcon, QPixmap

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────
# Khi chạy qua Nuitka onefile, sys.executable là path đến .exe
# Khi chạy dev (python gui.py), __file__ là path đến script
if getattr(sys, 'frozen', False) or '__compiled__' in dir():
    # Nuitka onefile extracts to a Temp folder (sys.executable points there),
    # but the actual installed files (ffmpeg, node_portable) are next to the original .exe
    PROJECT_ROOT = pathlib.Path(sys.argv[0]).parent.resolve()
else:
    PROJECT_ROOT = pathlib.Path(__file__).parent.resolve()

CONFIG_FILE  = PROJECT_ROOT / "gui_config.json"
STORYBOARDS  = PROJECT_ROOT / "storyboards"
OUTPUT_DIR   = PROJECT_ROOT / "output"
STORYBOARDS.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1a1b26;
    color: #c0caf5;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}
QTabWidget::pane {
    border: 1px solid #2a2b3d;
    background-color: #1a1b26;
    border-radius: 6px;
}
QTabBar::tab {
    background-color: #16161e;
    color: #7982a9;
    padding: 10px 22px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    font-weight: 500;
}
QTabBar::tab:selected {
    background-color: #1a1b26;
    color: #7aa2f7;
    border-bottom: 2px solid #7aa2f7;
}
QTabBar::tab:hover:!selected {
    background-color: #1f2033;
    color: #a9b1d6;
}
QGroupBox {
    border: 1px solid #2a2b3d;
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px;
    font-weight: 600;
    color: #7aa2f7;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #16161e;
    border: 1px solid #2a2b3d;
    border-radius: 5px;
    padding: 6px 10px;
    color: #c0caf5;
    selection-background-color: #364a82;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border: 1px solid #7aa2f7;
}
QPushButton {
    background-color: #364a82;
    color: #c0caf5;
    border: none;
    border-radius: 6px;
    padding: 8px 18px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #4a5faa;
}
QPushButton:pressed {
    background-color: #2a3a72;
}
QPushButton:disabled {
    background-color: #232433;
    color: #565f89;
}
QPushButton#btn_primary {
    background-color: #7aa2f7;
    color: #1a1b26;
}
QPushButton#btn_primary:hover {
    background-color: #9bbeff;
}
QPushButton#btn_primary:disabled {
    background-color: #2a3a72;
    color: #565f89;
}
QPushButton#btn_danger {
    background-color: #f7768e;
    color: #1a1b26;
}
QPushButton#btn_danger:hover {
    background-color: #ff9bab;
}
QPushButton#btn_success {
    background-color: #9ece6a;
    color: #1a1b26;
}
QPushButton#btn_success:hover {
    background-color: #b4e28a;
}
QComboBox {
    background-color: #16161e;
    border: 1px solid #2a2b3d;
    border-radius: 5px;
    padding: 6px 10px;
    color: #c0caf5;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #1f2033;
    color: #c0caf5;
    selection-background-color: #364a82;
}
QProgressBar {
    border: 1px solid #2a2b3d;
    border-radius: 5px;
    background-color: #16161e;
    text-align: center;
    color: #c0caf5;
    height: 18px;
}
QProgressBar::chunk {
    background-color: #7aa2f7;
    border-radius: 4px;
}
QScrollBar:vertical {
    background: #16161e;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #2a2b3d;
    border-radius: 4px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #364a82; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QLabel#label_title {
    font-size: 22px;
    font-weight: 700;
    color: #7aa2f7;
}
QLabel#label_subtitle {
    color: #7982a9;
    font-size: 12px;
}
QFrame#separator {
    background-color: #2a2b3d;
    max-height: 1px;
}
"""

# ──────────────────────────────────────────────
# Config helpers
# ──────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_config(cfg: dict):
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")

# ──────────────────────────────────────────────
# Worker threads
# ──────────────────────────────────────────────
class GenerateWorker(QObject):
    finished   = pyqtSignal(str)   # storyboard JSON string
    error      = pyqtSignal(str)
    log        = pyqtSignal(str)

    def __init__(self, api_key, mode, url_or_text, model, provider, language="Tiếng Việt",
                 dur_min=25, dur_max=32, n_scenes=6):
        super().__init__()
        self.api_key     = api_key
        self.mode        = mode
        self.url_or_text = url_or_text
        self.source      = url_or_text  # alias used in _build_prompt
        self.model       = model
        self.provider    = provider
        self.language    = language
        self.dur_min     = dur_min
        self.dur_max     = dur_max
        self.n_scenes    = n_scenes

    def run(self):
        try:
            # 1. Fetch content
            self.log.emit("🌐 Đang lấy nội dung từ URL…")
            content = self._fetch(self.url_or_text)
            self.log.emit(f"✅ Lấy được {len(content)} ký tự nội dung.")

            # 2. Build system + user prompt
            system_prompt, user_prompt = self._build_prompt(content)

            # 3. Call AI provider
            if self.provider == PROVIDER_GEMINI:
                raw = self._call_gemini(system_prompt, user_prompt)
            else:
                raw = self._call_claude(system_prompt, user_prompt)

            # 4. Extract JSON block
            self.log.emit("📝 Xử lý kết quả…")
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_match2 = re.search(r"(\{[\s\S]*\})", raw)
                if json_match2:
                    json_str = json_match2.group(1)
                else:
                    json_str = raw

            # validate
            parsed = json.loads(json_str)
            pretty = json.dumps(parsed, indent=2, ensure_ascii=False)
            self.log.emit("✅ Storyboard JSON đã sẵn sàng!")
            self.finished.emit(pretty)

        except Exception as e:
            self.error.emit(str(e))

    def _call_claude(self, system_prompt: str, user_prompt: str) -> str:
        import anthropic as ant
        self.log.emit(f"🤖 Gọi Claude ({self.model})…")
        client = ant.Anthropic(api_key=self.api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return msg.content[0].text

    def _call_gemini(self, system_prompt: str, user_prompt: str) -> str:
        from google import genai
        self.log.emit(f"🤖 Gọi Gemini ({self.model})…")
        client = genai.Client(api_key=self.api_key)
        full_prompt = system_prompt + "\n\n" + user_prompt
        response = client.models.generate_content(
            model=self.model,
            contents=full_prompt,
        )
        return response.text

    def _fetch(self, url_or_text: str) -> str:
        text = url_or_text.strip()
        if text.startswith("http://") or text.startswith("https://"):
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            try:
                resp = requests.get(text, headers=headers, timeout=15)
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in soup(["script","style","nav","footer","header","aside"]):
                    tag.decompose()
                body = soup.get_text(separator="\n", strip=True)
                return body[:8000]
            except Exception as e:
                return f"[Could not fetch URL: {e}] — URL: {text}"
        return text  # raw text / pasted content

    def _build_prompt(self, content: str):
        # Strip emoji flag from language label, e.g. "🇺🇳  Tiếng Việt" -> "Tiếng Việt"
        lang = self.language.split("  ", 1)[-1].strip() if "  " in self.language else self.language.strip()

        # Determine caption pair instructions based on language
        if "Việt" in lang:
            caption_instruction = (
                "- caption.en: tiêu đề ngắn <=10 từ tiếng Anh (dùng làm phụ đề/SEO)\n"
                "- caption.vi: 1–2 câu tường thuật tiếng Việt tự nhiên, đọc to rõ ràng"
            )
            lang_rule = (
                f"CRITICAL: The output language is {lang}. "
                "Write ALL on-screen text (headline, sub, stats labels, terminal lines, "
                "quote text, cta label) in Vietnamese. Only keep technical terms (CVE IDs, "
                "product names, URLs, version numbers) in their original form."
            )
        else:
            caption_instruction = (
                f"- caption.en: punchy ≤10-word {lang} headline (speakable)\n"
                f"- caption.vi: 1–2 {lang} narration sentences (full, natural spoken cadence)"
            )
            lang_rule = (
                f"CRITICAL: The output language is {lang}. "
                f"Write ALL on-screen text in {lang}."
            )

        # Scene type descriptions (shared)
        scene_types = (
            '- "hero-text":  {"emoji":"...","headline":"...","sub":"...","caption":{"en":"...","vi":"..."}}\n'
            '- "stats-grid": {"stats":[{"big":"...","label":"...","accent":true/false}],"caption":{...}}\n'
            '- "terminal":   {"title":"...","lines":[{"type":"prompt","text":"$ ..."}],"caption":{...}}\n'
            '- "code-diff":  {"badLabel":"...","bad":"...","goodLabel":"...","good":"...","caption":{...}}\n'
            '- "quote":      {"text":"...","attr":"...","caption":{...}}\n'
            '- "cta-url":    {"label":"...","url":"...","sub":"...","caption":{...}}'
        )

        if self.mode == "news":
            system = textwrap.dedent(f"""\
                You are an expert short-form video scriptwriter.
                {lang_rule}
                Return ONLY valid JSON in a ```json ... ``` block. No explanation outside the block.

                Output schema:
                {{
                  "meta": {{"title":"...","slug":"kebab-case","theme":"default|danger|warning|success","source":"url"}},
                  "scenes": [
                    {{"type":"<scene_type>","duration":<seconds>, ...scene_fields...,
                      "caption":{{"en":"...","vi":"..."}}}}
                    // repeat for ALL {self.n_scenes} scenes
                  ]
                }}

                Available scene types (each scene must include "type" and "duration"):
                {scene_types}

                STRICT RULES:
                - MUST produce EXACTLY {self.n_scenes} scenes.
                - Total sum of all durations MUST be between {self.dur_min} and {self.dur_max} seconds.
                - Vary scene types across the video — do NOT repeat the same type consecutively.
                - theme: "danger" for CVEs, "warning" for moderate issues, "success" for milestones, "default" otherwise.
                - {caption_instruction}
                - slug: kebab-case ASCII only.
            """)
            user = f"Create the storyboard for this tech news article:\n\n{content}"
        else:  # promo
            system = textwrap.dedent(f"""\
                You are an expert short-form video scriptwriter.
                {lang_rule}
                Return ONLY valid JSON in a ```json ... ``` block. No explanation outside the block.

                Output schema:
                {{
                  "meta": {{"title":"...","slug":"kebab-case","theme":"default|success","source":"url"}},
                  "scenes": [
                    {{"type":"<scene_type>","duration":<seconds>, ...scene_fields...,
                      "caption":{{"en":"...","vi":"..."}}}}
                    // repeat for ALL {self.n_scenes} scenes
                  ]
                }}

                Available scene types (each scene must include "type" and "duration"):
                {scene_types}

                STRICT RULES:
                - MUST produce EXACTLY {self.n_scenes} scenes.
                - Total sum of all durations MUST be between {self.dur_min} and {self.dur_max} seconds.
                - Vary scene types — start with hero-text, end with cta-url, mix others in between.
                - Highlight: star count, main feature, install command, key benefit.
                - theme: "success" for milestone repos, "default" otherwise.
                - {caption_instruction}
                - slug: kebab-case ASCII only.
            """)
            user = f"Create the promo storyboard for this GitHub project:\n\n{content}"

        return system, user


def _find_ffmpeg(custom_path: str = "") -> str:
    """Return path to ffmpeg executable, or empty string if not found."""
    ffmpeg_name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"

    # 0. Project-local ffmpeg folder (highest priority — bundled with project)
    for candidate in [
        PROJECT_ROOT / "ffmpeg" / ffmpeg_name,
        PROJECT_ROOT / "ffmpeg" / "bin" / ffmpeg_name,
        PROJECT_ROOT / ffmpeg_name,
    ]:
        if candidate.is_file():
            return str(candidate)

    # 1. User-provided path from Settings
    if custom_path:
        p = pathlib.Path(custom_path)
        if p.is_file():
            return str(p)
        exe = p / ffmpeg_name
        if exe.is_file():
            return str(exe)

    # 2. System PATH
    for name in ([ffmpeg_name, "ffmpeg"] if sys.platform == "win32" else ["ffmpeg"]):
        found = shutil.which(name)
        if found:
            return found

    # 3. Common install locations on Windows
    if sys.platform == "win32":
        for loc in [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]:
            if pathlib.Path(loc).is_file():
                return loc

    return ""


class RenderWorker(QObject):
    finished = pyqtSignal(str, str)  # path_16x9, path_9x16
    error    = pyqtSignal(str)
    log      = pyqtSignal(str)
    progress = pyqtSignal(int)

    def __init__(self, storyboard_path: str, formats: list, ffmpeg_path: str = "", video_theme: str = "cream"):
        super().__init__()
        self.storyboard_path = storyboard_path
        self.formats         = formats
        self.ffmpeg_path     = ffmpeg_path
        self.video_theme     = video_theme

    def run(self):
        try:
            spath = pathlib.Path(self.storyboard_path)
            with open(spath, encoding="utf-8") as f:
                data = json.load(f)

            slug  = data.get("meta", {}).get("slug", "video")
            date  = datetime.datetime.now().strftime("%Y-%m-%d")
            out   = OUTPUT_DIR / f"{date}-{slug}"
            raw   = PROJECT_ROOT / "videos-raw"

            if raw.exists():
                shutil.rmtree(raw)

            env = os.environ.copy()
            rel_path = str(spath.relative_to(PROJECT_ROOT)).replace("\\", "/")
            env["STORYBOARD_PATH"] = rel_path
            env["STORYBOARD_SLUG"] = slug
            env["VIDEO_FORMATS"]   = ",".join(self.formats)
            env["VIDEO_THEME"]     = self.video_theme

            # ── Dùng Node.js portable nếu có (bundle trong app) ──
            node_portable = PROJECT_ROOT / "node_portable"
            if node_portable.exists():
                npx = str(node_portable / "npx.cmd")
                env["PATH"] = str(node_portable) + os.pathsep + env.get("PATH", "")
            else:
                npx = "npx.cmd" if sys.platform == "win32" else "npx"

            # ── Playwright browsers: dùng thư mục bundle nếu có ──
            pw_browsers = PROJECT_ROOT / "playwright-browsers"
            if pw_browsers.exists():
                env["PLAYWRIGHT_BROWSERS_PATH"] = str(pw_browsers)

            ffmpeg = _find_ffmpeg(self.ffmpeg_path)
            if not ffmpeg:
                self.error.emit("❌ Không tìm thấy ffmpeg!")
                return

            self.log.emit("🎬 Đang ghi hình bằng Playwright…")
            proc = subprocess.Popen(
                [npx, "playwright", "test"],
                env=env, cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace"
            )
            for line in proc.stdout:
                if line.rstrip(): self.log.emit(line.rstrip())
            proc.wait()

            if proc.returncode != 0:
                self.error.emit("Playwright thất bại.")
                return

            out.mkdir(parents=True, exist_ok=True)
            path_16x9 = path_9x16 = None
            for webm in raw.rglob("video.webm"):
                proj = webm.parent.name
                if "16x9" in proj:
                    if "16x9" not in self.formats:
                        continue   # user did not select this format
                    dst = out / f"{slug}-16x9.mp4"
                    path_16x9 = str(dst)
                elif "9x16" in proj:
                    if "9x16" not in self.formats:
                        continue   # user did not select this format
                    dst = out / f"{slug}-9x16.mp4"
                    path_9x16 = str(dst)
                else:
                    continue

                self.log.emit(f"🔄  ffmpeg: {webm.parent.name} → {dst.name}")
                cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                subprocess.run(
                    [ffmpeg, "-y", "-nostdin", "-i", str(webm),
                     "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p",
                     "-movflags", "+faststart", str(dst)],
                    check=True, creationflags=cflags
                )

            self.log.emit(f"✅ Xong! Định dạng xuất: {', '.join(self.formats)}")
            self.finished.emit(path_16x9 or "", path_9x16 or "")
        except Exception as e:
            self.error.emit(str(e))



GEMINI_TTS_VOICES = [
    "Zephyr", "Puck", "Charon", "Kore", "Fenrir", "Leda", "Orus", "Aoede",
    "Callirrhoe", "Autonoe", "Enceladus", "Iapetus", "Umbriel", "Algieba",
    "Despina", "Erinome", "Algenib", "Rasalhauge", "Laomedeia", "Achernar",
    "Alnilam", "Schedar", "Gacrux", "Pulcherrima", "Achird",
    "Zubenelgenubi", "Vindemiatrix", "Sadachbia", "Sadaltager", "Sulafat",
]


class GeminiTTSWorker(QObject):
    """TTS using Google Gemini API — generates audio once, muxes into ALL video paths."""
    finished = pyqtSignal(list)   # list of output file paths
    error    = pyqtSignal(str)
    log      = pyqtSignal(str)

    def __init__(self, api_key, storyboard_path, video_paths,
                 voice_name="Kore", ffmpeg_path=""):
        super().__init__()
        self.api_key         = api_key
        self.storyboard_path = storyboard_path
        # Accept single path or list
        self.video_paths     = video_paths if isinstance(video_paths, list) else [video_paths]
        self.voice_name      = voice_name
        self.ffmpeg_path     = ffmpeg_path

    def run(self):
        try:
            import pathlib, json, subprocess, wave, base64, shutil
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)

            # Use first video's folder for tmp dir
            first_video = pathlib.Path(self.video_paths[0])
            video_dir   = first_video.parent
            tmp         = video_dir / "tts_tmp_gemini"
            tmp.mkdir(exist_ok=True)
            ffmpeg      = _find_ffmpeg(self.ffmpeg_path)

            # ── Build script from storyboard captions ──
            with open(self.storyboard_path, encoding="utf-8") as f:
                data = json.load(f)
            scenes = data.get("scenes", [])
            parts  = []
            for scene in scenes:
                text = (scene.get("caption", {}).get("vi")
                        or scene.get("caption", {}).get("en") or "")
                if text:
                    parts.append(text.strip().rstrip(".") + ".")

            full_script = " ".join(parts)
            total_dur   = sum(s.get("duration", 4) for s in scenes)
            self.log.emit(f"🔊 Gemini TTS cho {len(scenes)} scene ({total_dur}s) — {len(self.video_paths)} video…")

            # ── Single API call ──
            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=full_script,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=self.voice_name
                            )
                        )
                    )
                )
            )

            raw         = response.candidates[0].content.parts[0].inline_data.data
            audio_bytes = base64.b64decode(raw) if isinstance(raw, str) else bytes(raw)
            if len(audio_bytes) < 100:
                raise ValueError(f"Audio trống ({len(audio_bytes)} bytes)")
            self.log.emit(f"  ✅ {len(audio_bytes)//1024} KB audio")

            # Ghi WAV → MP3
            full_wav  = tmp / "voice.wav"
            voice_mp3 = tmp / "voice.mp3"
            with wave.open(str(full_wav), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(audio_bytes)
            cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.run([ffmpeg, "-y", "-i", str(full_wav), str(voice_mp3)],
                           check=True, capture_output=True, creationflags=cflags)

            # ── Mux audio vào tất cả video ──
            out_paths = []
            for vpath in self.video_paths:
                vpath     = pathlib.Path(vpath)
                out_final = str(vpath.parent / (vpath.stem + "-final.mp4"))
                self.log.emit(f"  🎥 Ghép giọng → {vpath.name}…")
                cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                subprocess.run([
                    ffmpeg, "-y",
                    "-i", str(vpath),
                    "-i", str(voice_mp3),
                    "-c:v", "copy", "-c:a", "aac",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-shortest", out_final
                ], check=True, capture_output=True, creationflags=cflags)
                out_paths.append(out_final)
                # Xóa video không có giọng
                try: vpath.unlink()
                except Exception: pass

            # Xóa thư mục tmp
            shutil.rmtree(tmp, ignore_errors=True)
            self.log.emit("✅ Voice-over hoàn thành!")
            self.finished.emit(out_paths)
        except Exception as e:
            self.error.emit(str(e))


def _el_error_msg(raw: str) -> str:
    """Translate ElevenLabs API error to user-friendly Vietnamese message."""
    if "paid_plan_required" in raw or "payment_required" in raw or "402" in raw:
        if "library" in raw.lower():
            return (
                "🔒  Lỗi: Giọng này là Library Voice (cộng đồng), không dùng API free được.\n\n"
                "ElevenLabs phân biệt hai loại trong 'My Voices':\n"
                "  ✅ Personal Voice = bạn tự tạo/clone → dùng API miễn phíđược\n"
                "  ❌ Library Voice = giọng bạn lưu từ Voice Library → cần Starter+ để dùng API\n\n"
                "Cách kiểm tra:\n"
                "  1. Vào elevenlabs.io → My Voices\n"
                "  2. Chọn giọng → xem tab 'Settings'\n"
                "  3. Nếu là 'Cloned Voice' hoặc 'Generated' = dùng được\n"
                "  4. Nếu là 'Voice Library' / có biểu tượng cộng đồng = cần nâng cấp\n\n"
                f"Lỗi gốc: {raw[:150]}"
            )
        return (
            "🔒  Tài khoản ElevenLabs cần nâng cấp để dùng tính năng này.\n\n"
            f"Chi tiết: {raw[:200]}"
        )
    if "invalid_api_key" in raw or "401" in raw:
        return "🔑  API Key không hợp lệ hoặc đã hết hạn. Kiểm tra lại key trong tab ⚙️ Cài đặt."
    if "voice_not_found" in raw or "404" in raw:
        return "❓  Không tìm thấy Voice ID này. Kiểm tra lại Voice ID trong tab ⚙️ Cài đặt."
    if "quota_exceeded" in raw or "429" in raw:
        return "⏱️  Đã hết quota ký tự tháng này. Nâng cấp gói hoặc chờ tháng sau."
    return raw


class _TestVoiceWorker(QObject):

    """Calls ElevenLabs TTS with a short sentence to verify voice + model work."""
    success = pyqtSignal(str)   # voice_id
    error   = pyqtSignal(str)

    def __init__(self, api_key, voice_id, tts_model):
        super().__init__()
        self.api_key   = api_key
        self.voice_id  = voice_id
        self.tts_model = tts_model

    def run(self):
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=self.api_key)
            audio = client.text_to_speech.convert(
                text="Đây là bài kiểm tra giọng.",
                voice_id=self.voice_id,
                model_id=self.tts_model,
                output_format="mp3_44100_128",
            )
            # Consume the generator to trigger actual API call
            for _ in audio:
                break
            self.success.emit(self.voice_id)
        except Exception as e:
            self.error.emit(_el_error_msg(str(e)))


class VoiceWorker(QObject):
    finished = pyqtSignal(str)   # path to merged mp4
    error    = pyqtSignal(str)
    log      = pyqtSignal(str)

    def __init__(self, api_key, voice_id, storyboard_path, video_path, tts_model="eleven_turbo_v2_5", ffmpeg_path=""):
        super().__init__()
        self.api_key         = api_key
        self.voice_id        = voice_id
        self.storyboard_path = storyboard_path
        self.video_path      = video_path
        self.tts_model       = tts_model
        self.ffmpeg_path     = ffmpeg_path

    def run(self):
        try:
            from elevenlabs.client import ElevenLabs
            client = ElevenLabs(api_key=self.api_key)

            with open(self.storyboard_path, encoding="utf-8") as f:
                data = json.load(f)

            scenes = data.get("scenes", [])
            tmp    = pathlib.Path(self.video_path).parent / "tts_tmp"
            tmp.mkdir(exist_ok=True)

            clips = []
            for i, scene in enumerate(scenes):
                text = scene.get("caption", {}).get("vi") or "..."
                dur = scene.get("duration", 4)
                audio = client.text_to_speech.convert(
                    text=text,
                    voice_id=self.voice_id,
                    model_id=self.tts_model,
                    output_format="mp3_44100_128",
                )

                clip_path = tmp / f"clip_{i+1}.mp3"
                with open(clip_path, "wb") as af:
                    for chunk in audio: af.write(chunk)
                clips.append((clip_path, dur))

            ffmpeg = _find_ffmpeg(self.ffmpeg_path)
            inputs = []
            filter_parts = []
            for idx, (cp, dur) in enumerate(clips):
                inputs += ["-i", str(cp)]
                filter_parts.append(f"[{idx}:a]apad=whole_dur={dur}[a{idx}]")
            
            concat_inputs = "".join(f"[a{i}]" for i in range(len(clips)))
            filter_str = ";".join(filter_parts) + f";{concat_inputs}concat=n={len(clips)}:v=0:a=1[out]"
            voice_mp3 = tmp / "voice.mp3"

            cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.run([ffmpeg, "-y", *inputs, "-filter_complex", filter_str, "-map", "[out]", str(voice_mp3)], check=True, capture_output=True, creationflags=cflags)
            out_final = pathlib.Path(self.video_path).with_suffix("").as_posix() + "-with-voice.mp4"
            subprocess.run([ffmpeg, "-y", "-i", self.video_path, "-i", str(voice_mp3), "-c:v", "copy", "-c:a", "aac", "-shortest", out_final], check=True, capture_output=True, creationflags=cflags)
            self.finished.emit(out_final)
        except Exception as e:
            self.error.emit(_el_error_msg(str(e)))



# ──────────────────────────────────────────────
# ElevenLabs voice list worker
# ──────────────────────────────────────────────
class _VoiceListWorker(QObject):
    finished = pyqtSignal(list)   # list of (name, voice_id)
    error    = pyqtSignal(str)

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def run(self):
        try:
            resp = requests.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": self.api_key},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            voices = [(v["name"], v["voice_id"]) for v in data.get("voices", [])]
            voices.sort(key=lambda x: x[0].lower())
            self.finished.emit(voices)
        except Exception as e:
            self.error.emit(str(e))


# ──────────────────────────────────────────────
# Main Window
# ──────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.cfg = load_config()
        self._gen_thread  = None
        self._ren_thread  = None
        self._voi_thread  = None
        self._storyboard_path = None
        self._video_16x9  = None
        self._video_9x16  = None

        self.setWindowTitle("AI Shorts Generator")
        self.setMinimumSize(1050, 750)
        self.resize(1200, 850)
        self.setStyleSheet(DARK_STYLE)

        # App icon
        _icon_path = str(PROJECT_ROOT / "logo.ico")
        if pathlib.Path(_icon_path).exists():
            self.setWindowIcon(QIcon(_icon_path))

        self._build_ui()
        self._load_cfg_to_ui()

    # ── UI construction ──────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("🎬 AI Shorts Generator")
        title.setObjectName("label_title")
        sub = QLabel("Tạo video Short từ tin tức / GitHub repo • Powered by Lý Trần")
        sub.setObjectName("label_subtitle")
        hdr.addWidget(title)
        hdr.addStretch()
        hdr.addWidget(sub)
        root.addLayout(hdr)

        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        # Tabs
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        self.tabs.addTab(self._build_settings_tab(),   "⚙️  Cài đặt")
        self.tabs.addTab(self._build_generate_tab(),   "✍️  Tạo Storyboard")
        self.tabs.addTab(self._build_render_tab(),     "🎥  Render & Voice")

    # ─── Settings Tab ───────────────────────────
    def _build_settings_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(18)

        # AI Provider selector
        grp_provider = QGroupBox("🤖  Chọn AI Provider")
        prov_lay = QVBoxLayout(grp_provider)
        prov_lay.setSpacing(8)

        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("Provider:"))
        self.cmb_provider = QComboBox()
        self.cmb_provider.addItems([PROVIDER_CLAUDE, PROVIDER_GEMINI])
        self.cmb_provider.currentIndexChanged.connect(self._on_provider_changed)
        prov_row.addWidget(self.cmb_provider)
        prov_row.addStretch()
        prov_lay.addLayout(prov_row)
        lay.addWidget(grp_provider)

        # Claude settings
        self.grp_claude = QGroupBox("🔑  Claude (Anthropic) — API Key & Model")
        form_c = QFormLayout(self.grp_claude)
        form_c.setSpacing(10)

        self.inp_anthropic_key = QLineEdit()
        self.inp_anthropic_key.setPlaceholderText("sk-ant-api03-...")
        self.inp_anthropic_key.setEchoMode(QLineEdit.Password)

        self.cmb_claude_model = QComboBox()
        self.cmb_claude_model.addItems([
            "claude-opus-4-5",
            "claude-sonnet-4-5",
            "claude-haiku-4-5",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ])

        form_c.addRow("API Key:", self.inp_anthropic_key)
        form_c.addRow("Model:", self.cmb_claude_model)
        lay.addWidget(self.grp_claude)

        # Gemini settings
        self.grp_gemini = QGroupBox("🔑  Gemini (Google) — API Key & Model")
        form_g = QFormLayout(self.grp_gemini)
        form_g.setSpacing(10)

        self.inp_gemini_key = QLineEdit()
        self.inp_gemini_key.setPlaceholderText("AIza...")
        self.inp_gemini_key.setEchoMode(QLineEdit.Password)

        self.cmb_gemini_model = QComboBox()
        self.cmb_gemini_model.addItems([
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-2.0-flash",
            "gemini-flash-latest",
            "gemini-pro-latest",
        ])
        help_lbl = QLabel("💡 Gemini 2.0 Flash có free tier rất rộng rãi (không cần trả tiền)")
        help_lbl.setStyleSheet("color:#9ece6a; font-size:11px;")

        form_g.addRow("API Key:", self.inp_gemini_key)
        form_g.addRow("Model:", self.cmb_gemini_model)
        form_g.addRow("", help_lbl)
        lay.addWidget(self.grp_gemini)
        self.grp_gemini.hide()  # hidden by default

        # Output Language
        grp_lang = QGroupBox("🌍  Ngôn ngữ Video Output")
        form_l = QFormLayout(grp_lang)
        form_l.setSpacing(10)

        self.cmb_language = QComboBox()
        self.cmb_language.addItems([
            "🇺🇳  Tiếng Việt",
            "🇬🇧  English",
            "🇨🇳  中文 (Chinese)",
            "🇯🇵  日本語 (Japanese)",
            "🇰🇷  한국어 (Korean)",
            "🇫🇷  Français",
            "🇪🇸  Español",
            "🇩🇪  Deutsch",
        ])
        lang_hint = QLabel("💡 Chọn ngôn ngữ, AI sẽ viết toàn bộ nội dung video (headline, caption, thống kê...) bằng ngôn ngữ đó.")
        lang_hint.setStyleSheet("color:#7982a9; font-size:11px;")
        lang_hint.setWordWrap(True)
        form_l.addRow("Ngôn ngữ:", self.cmb_language)
        form_l.addRow("", lang_hint)
        lay.addWidget(grp_lang)

        # Video Visual Theme
        grp_theme = QGroupBox("🎨  Phông nền Video")
        form_t = QFormLayout(grp_theme)
        form_t.setSpacing(10)
        self.cmb_video_theme = QComboBox()
        themes = [
            ("cream",    "🧈  Cream — nền kem ấm ánh vàng"),
            ("dark",     "🌌  Dark — nền đen xanh navy"),
            ("ocean",    "🌊  Ocean — nền biển sâu"),
            ("midnight", "🔮  Midnight — đen neon tím"),
            ("forest",   "🌲  Forest — xanh lá tối"),
            ("rose",     "🌹  Rose — hồng coral"),
        ]
        for val, label in themes:
            self.cmb_video_theme.addItem(label, userData=val)
        theme_hint = QLabel("💡 Phông nền sẽ áp dụng cho toàn bộ video khi render.")
        theme_hint.setStyleSheet("color:#7982a9; font-size:11px;")
        theme_hint.setWordWrap(True)
        form_t.addRow("Theme:", self.cmb_video_theme)
        form_t.addRow("", theme_hint)
        lay.addWidget(grp_theme)

        # TTS Voice-over section
        grp_el = QGroupBox("🎤  Voice-over — TTS Provider")
        el_lay = QVBoxLayout(grp_el)
        el_lay.setSpacing(12)
        el_lay.setContentsMargins(10, 14, 10, 10)

        # ── TTS Provider chọn ──
        prov_lbl = QLabel("🔊  Chọn TTS Provider:")
        prov_lbl.setStyleSheet("font-weight:600; color:#c0caf5;")
        el_lay.addWidget(prov_lbl)

        prov_row = QHBoxLayout()
        self.rb_tts_google = QRadioButton("🤖  Gemini TTS (dùng chung API key Gemini)")
        self.rb_tts_eleven = QRadioButton("🎤  ElevenLabs (API Key riêng)")
        self.rb_tts_google.setChecked(True)
        prov_row.addWidget(self.rb_tts_google)
        prov_row.addWidget(self.rb_tts_eleven)
        prov_row.addStretch()
        el_lay.addLayout(prov_row)

        # Gemini TTS voice picker (visible when Gemini selected)
        self.grp_gemini_tts = QWidget()
        gemini_tts_lay = QHBoxLayout(self.grp_gemini_tts)
        gemini_tts_lay.setContentsMargins(0, 4, 0, 0)
        gemini_tts_lay.addWidget(QLabel("Giọng:"))
        self.cmb_gemini_voice = QComboBox()
        self.cmb_gemini_voice.addItems(GEMINI_TTS_VOICES)
        self.cmb_gemini_voice.setCurrentText("Kore")  # default: neutral
        gemini_tts_lay.addWidget(self.cmb_gemini_voice)
        gemini_tts_lay.addStretch()
        gemini_hint = QLabel("💡 Dùng chung Gemini API Key • 30 giọng • Hỗ trợ tiếng Việt tốt")
        gemini_hint.setStyleSheet("color:#9ece6a; font-size:11px;")
        gemini_tts_lay.addWidget(gemini_hint)
        el_lay.addWidget(self.grp_gemini_tts)

        self.rb_tts_google.toggled.connect(lambda on: self.grp_gemini_tts.setVisible(on))
        self.rb_tts_google.toggled.connect(lambda on: self.grp_eleven_settings.setVisible(not on))

        # Container cho ElevenLabs settings (ẩn/hiện theo provider)
        self.grp_eleven_settings = QWidget()
        eleven_inner = QVBoxLayout(self.grp_eleven_settings)
        eleven_inner.setContentsMargins(0, 6, 0, 0)
        eleven_inner.setSpacing(10)

        # API Key
        key_form = QFormLayout()
        key_form.setSpacing(8)
        self.inp_elevenlabs_key = QLineEdit()
        self.inp_elevenlabs_key.setPlaceholderText("Nhập ElevenLabs API Key...")
        self.inp_elevenlabs_key.setEchoMode(QLineEdit.Password)
        key_form.addRow("API Key:", self.inp_elevenlabs_key)
        eleven_inner.addLayout(key_form)

        div1 = QFrame(); div1.setFrameShape(QFrame.HLine)
        div1.setStyleSheet("QFrame { background-color: #2a2b3d; max-height: 1px; }")
        eleven_inner.addWidget(div1)

        # Mode 1: Chọn từ danh sách
        self.rb_voice_list = QRadioButton("🔊  Chọn giọng từ danh sách API")
        self.rb_voice_list.setChecked(True)
        eleven_inner.addWidget(self.rb_voice_list)

        mode1_row = QHBoxLayout()
        mode1_row.setContentsMargins(28, 2, 0, 8)
        mode1_row.setSpacing(8)
        self.cmb_voice = QComboBox()
        self.cmb_voice.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cmb_voice.setPlaceholderText("(Nhấn 'Tải giọng' để load danh sách)")
        self.cmb_voice.currentIndexChanged.connect(self._on_voice_selected)
        self.btn_load_voices = QPushButton("🔄  Tải giọng")
        self.btn_load_voices.setFixedWidth(120)
        self.btn_load_voices.clicked.connect(self._load_voices)
        mode1_row.addWidget(self.cmb_voice)
        mode1_row.addWidget(self.btn_load_voices)
        eleven_inner.addLayout(mode1_row)

        # Mode 2: Nhập Voice ID thủ công
        self.rb_voice_id = QRadioButton("✏️  Nhập Voice ID thủ công")
        eleven_inner.addWidget(self.rb_voice_id)

        mode2_row = QHBoxLayout()
        mode2_row.setContentsMargins(28, 2, 0, 0)
        self.inp_voice_id = QLineEdit()
        self.inp_voice_id.setPlaceholderText("Voice ID (vd: pNInz6obpgDQGcFmaJgB)")
        self.inp_voice_id.setEnabled(False)
        mode2_row.addWidget(self.inp_voice_id)
        eleven_inner.addLayout(mode2_row)

        # Mutual exclusion radios
        self._voice_bg = QButtonGroup(grp_el)
        self._voice_bg.addButton(self.rb_voice_list, 0)
        self._voice_bg.addButton(self.rb_voice_id,   1)
        self._voice_bg.buttonClicked.connect(self._on_voice_mode_changed)

        # TTS Model
        div2 = QFrame(); div2.setFrameShape(QFrame.HLine)
        div2.setStyleSheet("QFrame { background-color: #2a2b3d; max-height: 1px; }")
        eleven_inner.addWidget(div2)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("TTS Model:"))
        self.cmb_tts_model = QComboBox()
        self.cmb_tts_model.addItems([
            "eleven_v3",
            "eleven_turbo_v2_5",
            "eleven_flash_v2_5",
            "eleven_multilingual_v2",
            "eleven_monolingual_v1",
        ])
        self.cmb_tts_model.setCurrentIndex(0)
        model_hint = QLabel("💡 eleven_v3 = mới nhất theo docs | turbo/flash = free tier")
        model_hint.setStyleSheet("color:#7982a9; font-size:10px;")
        model_row.addWidget(self.cmb_tts_model)
        eleven_inner.addLayout(model_row)
        eleven_inner.addWidget(model_hint)

        # Test voice button
        btn_test_voice = QPushButton("🔍  Kiểm tra giọng ElevenLabs")
        btn_test_voice.setObjectName("btn_secondary")
        btn_test_voice.clicked.connect(self._test_voice)
        self.btn_test_voice = btn_test_voice
        eleven_inner.addWidget(btn_test_voice)

        el_lay.addWidget(self.grp_eleven_settings)
        self.grp_eleven_settings.setVisible(False)  # Google TTS mặc định

        lay.addWidget(grp_el)

        lay.addStretch()

        # ── Wrap inner widget in ScrollArea ──
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollBar:vertical { width: 6px; background: #1a1b2e; border-radius: 3px; } QScrollBar::handle:vertical { background: #364a82; border-radius: 3px; min-height: 20px; }")
        scroll.setWidget(w)

        # Outer container with scroll + pinned save button
        outer = QWidget()
        out_lay = QVBoxLayout(outer)
        out_lay.setContentsMargins(0, 0, 0, 10)
        out_lay.setSpacing(8)
        out_lay.addWidget(scroll)

        btn_save = QPushButton("💾  Lưu cấu hình")
        btn_save.setObjectName("btn_primary")
        btn_save.clicked.connect(self._save_cfg)
        out_lay.addWidget(btn_save, alignment=Qt.AlignRight)

        return outer

    # ─── Generate Tab ───────────────────────────
    def _build_generate_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        # Input group
        grp_in = QGroupBox("🔗  Nguồn nội dung")
        in_lay = QVBoxLayout(grp_in)
        in_lay.setSpacing(8)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Loại video:"))
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["📰  Tin tức công nghệ (News)", "🚀  Giới thiệu GitHub Repo (Promo)"])
        mode_row.addWidget(self.cmb_mode)
        mode_row.addStretch()
        mode_row.addWidget(QLabel("⏱ Độ dài:"))
        self.cmb_duration = QComboBox()
        self.cmb_duration.addItems(["~30 giây (6 scene)", "~60 giây (10 scene)", "~90 giây (15 scene)", "~120 giây (20 scene)"])
        self.cmb_duration.setFixedWidth(185)
        mode_row.addWidget(self.cmb_duration)
        in_lay.addLayout(mode_row)

        self.inp_url = QLineEdit()
        self.inp_url.setPlaceholderText("Dán URL bài viết / GitHub repo tại đây…")
        in_lay.addWidget(self.inp_url)

        in_lay.addWidget(QLabel("Hoặc dán nội dung văn bản trực tiếp (nếu URL không truy cập được):"))
        self.txt_paste = QTextEdit()
        self.txt_paste.setPlaceholderText("Dán nội dung bài viết / README / mô tả dự án vào đây…")
        self.txt_paste.setMaximumHeight(100)
        in_lay.addWidget(self.txt_paste)

        btn_gen = QPushButton("✨  Tạo Storyboard bằng AI")
        btn_gen.setObjectName("btn_primary")
        btn_gen.clicked.connect(self._do_generate)
        self.btn_gen = btn_gen
        in_lay.addWidget(btn_gen)
        lay.addWidget(grp_in)

        # Log
        grp_log = QGroupBox("📋  Log")
        log_lay = QVBoxLayout(grp_log)
        self.gen_log = QPlainTextEdit()
        self.gen_log.setReadOnly(True)
        self.gen_log.setMaximumHeight(90)
        self.gen_log.setFont(QFont("Consolas", 11))
        log_lay.addWidget(self.gen_log)
        lay.addWidget(grp_log)

        # JSON output
        grp_json = QGroupBox("📄  Storyboard JSON (có thể chỉnh sửa trực tiếp)")
        json_lay = QVBoxLayout(grp_json)
        self.txt_json = QPlainTextEdit()
        self.txt_json.setFont(QFont("Consolas", 12))
        self.txt_json.setPlaceholderText("Storyboard JSON sẽ hiện tại đây sau khi AI tạo xong…")
        json_lay.addWidget(self.txt_json)

        btn_row = QHBoxLayout()
        btn_load = QPushButton("📂  Load JSON có sẵn")
        btn_load.clicked.connect(self._load_json_file)
        btn_save_json = QPushButton("💾  Lưu & Chuyển sang Render")
        btn_save_json.setObjectName("btn_success")
        btn_save_json.clicked.connect(self._save_json_and_switch)
        btn_row.addWidget(btn_load)
        btn_row.addStretch()
        btn_row.addWidget(btn_save_json)
        json_lay.addLayout(btn_row)
        lay.addWidget(grp_json)

        return w

    # ─── Render Tab (merged with Voice-over) ──────────────
    def _build_render_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(12)

        # ── Storyboard ──
        grp_sb = QGroupBox("📄  Storyboard")
        sb_lay = QHBoxLayout(grp_sb)
        sb_lay.setSpacing(10)
        self.lbl_storyboard = QLabel("(chưa chọn)")
        self.lbl_storyboard.setStyleSheet("color:#9ece6a;")
        self.lbl_storyboard.setWordWrap(True)
        btn_choose_sb = QPushButton("📂  Chọn Storyboard…")
        btn_choose_sb.setFixedWidth(170)
        btn_choose_sb.clicked.connect(self._choose_storyboard)
        sb_lay.addWidget(self.lbl_storyboard, 1)
        sb_lay.addWidget(btn_choose_sb)
        lay.addWidget(grp_sb)

        # ── Format ──
        grp_fmt = QGroupBox("📰  Định dạng xuất")
        fmt_lay = QHBoxLayout(grp_fmt)
        fmt_lay.setSpacing(30)
        self.chk_16x9 = QCheckBox("🖥️  16:9  (Landscape / YouTube)")
        self.chk_16x9.setChecked(True)
        self.chk_9x16 = QCheckBox("📱  9:16  (Portrait / Shorts / Reels / TikTok)")
        self.chk_9x16.setChecked(True)
        fmt_lay.addWidget(self.chk_16x9)
        fmt_lay.addWidget(self.chk_9x16)
        fmt_lay.addStretch()
        lay.addWidget(grp_fmt)

        # Voice-over tích hợp
        grp_vo = QGroupBox("🎤  Voice-over (tùy chọn)")
        vo_lay = QVBoxLayout(grp_vo)
        vo_lay.setSpacing(10)

        vo_top = QHBoxLayout()
        self.chk_voiceover = QCheckBox("  Tự động ghép Voice-over sau khi render xong")
        self.chk_voiceover.setChecked(True)
        vo_top.addWidget(self.chk_voiceover)
        vo_top.addStretch()
        vo_lay.addLayout(vo_top)
        lay.addWidget(grp_vo)

        # ── Nút bấm ──
        self.btn_render = QPushButton("▶️  Bắt đầu Render")
        self.btn_render.setObjectName("btn_primary")
        self.btn_render.clicked.connect(self._do_render)
        lay.addWidget(self.btn_render)

        self.render_progress = QProgressBar()
        self.render_progress.setValue(0)
        lay.addWidget(self.render_progress)

        # ── Log ──
        grp_log_r = QGroupBox("📋  Log")
        log_r_lay = QVBoxLayout(grp_log_r)
        self.render_log = QPlainTextEdit()
        self.render_log.setReadOnly(True)
        self.render_log.setFont(QFont("Consolas", 11))
        log_r_lay.addWidget(self.render_log)
        lay.addWidget(grp_log_r)

        # ── Output ──
        grp_out = QGroupBox("📁  Đầu ra")
        out_lay = QFormLayout(grp_out)
        out_lay.setSpacing(8)
        self.lbl_out_16x9 = QLabel("—")
        self.lbl_out_16x9.setStyleSheet("color:#7aa2f7;")
        self.lbl_out_16x9.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_out_9x16 = QLabel("—")
        self.lbl_out_9x16.setStyleSheet("color:#7aa2f7;")
        self.lbl_out_9x16.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.lbl_vo_out = QLabel("—")
        self.lbl_vo_out.setStyleSheet("color:#9ece6a;")
        self.lbl_vo_out.setTextInteractionFlags(Qt.TextSelectableByMouse)
        out_lay.addRow("Video 16:9:",    self.lbl_out_16x9)
        out_lay.addRow("Video 9:16:",    self.lbl_out_9x16)
        out_lay.addRow("🎤 Voice-over:",  self.lbl_vo_out)
        btn_open = QPushButton("📂  Mở thư mục output")
        btn_open.clicked.connect(self._open_output_dir)
        out_lay.addRow("", btn_open)
        lay.addWidget(grp_out)
        return w


    # ──────────────────────────────────────────────
    # Config helpers
    # ──────────────────────────────────────────────
    def _on_provider_changed(self, idx):
        provider = self.cmb_provider.currentText()
        if provider == PROVIDER_GEMINI:
            self.grp_claude.hide()
            self.grp_gemini.show()
        else:
            self.grp_gemini.hide()
            self.grp_claude.show()

    def _load_cfg_to_ui(self):
        c = self.cfg
        self.inp_anthropic_key.setText(c.get("anthropic_key", ""))
        self.inp_gemini_key.setText(c.get("gemini_key", ""))
        self.inp_elevenlabs_key.setText(c.get("elevenlabs_key", ""))
        self.inp_voice_id.setText(c.get("voice_id", "pNInz6obpgDQGcFmaJgB"))
        # Provider
        provider = c.get("provider", PROVIDER_CLAUDE)
        idx = self.cmb_provider.findText(provider)
        if idx >= 0:
            self.cmb_provider.setCurrentIndex(idx)
        self._on_provider_changed(0)   # sync visibility
        # Models
        cm = c.get("claude_model", "claude-sonnet-4-5")
        ci = self.cmb_claude_model.findText(cm)
        if ci >= 0:
            self.cmb_claude_model.setCurrentIndex(ci)
        gm = c.get("gemini_model", "gemini-2.5-flash")
        gi = self.cmb_gemini_model.findText(gm)
        if gi >= 0:
            self.cmb_gemini_model.setCurrentIndex(gi)
        # ElevenLabs voice
        saved_voice_id   = c.get("voice_id", "")
        saved_voice_name = c.get("voice_name", "")
        voice_mode       = c.get("voice_mode", "list")  # "list" or "manual"
        # Restore radio mode
        if voice_mode == "manual":
            self.rb_voice_id.setChecked(True)
            self.inp_voice_id.setEnabled(True)
            self.cmb_voice.setEnabled(False)
            self.btn_load_voices.setEnabled(False)
            self.inp_voice_id.setText(saved_voice_id)
        else:
            self.rb_voice_list.setChecked(True)
            self.inp_voice_id.setEnabled(False)
            self.cmb_voice.setEnabled(True)
            self.btn_load_voices.setEnabled(True)
            if saved_voice_name and saved_voice_id:
                self.cmb_voice.addItem(f"{saved_voice_name}  [{saved_voice_id}]", userData=saved_voice_id)
                self.cmb_voice.setCurrentIndex(0)
        # Auto-load voices if key already saved and in list mode
        if c.get("elevenlabs_key") and voice_mode != "manual":
            QTimer.singleShot(800, self._load_voices)
        # TTS Model
        tm = c.get("tts_model", "eleven_v3")
        ti = self.cmb_tts_model.findText(tm)
        if ti >= 0:
            self.cmb_tts_model.setCurrentIndex(ti)
        # TTS Provider
        if c.get("tts_provider", "gemini") == "elevenlabs":
            self.rb_tts_eleven.setChecked(True)
            self.grp_gemini_tts.setVisible(False)
            self.grp_eleven_settings.setVisible(True)
        else:
            self.rb_tts_google.setChecked(True)
            self.grp_gemini_tts.setVisible(True)
            self.grp_eleven_settings.setVisible(False)
        # Gemini TTS voice
        gv = c.get("gemini_voice", "Kore")
        gi = self.cmb_gemini_voice.findText(gv)
        if gi >= 0:
            self.cmb_gemini_voice.setCurrentIndex(gi)
        # Video theme
        saved_theme = c.get("video_theme", "cream")
        for i in range(self.cmb_video_theme.count()):
            if self.cmb_video_theme.itemData(i) == saved_theme:
                self.cmb_video_theme.setCurrentIndex(i)
                break

    def _save_cfg(self):
        # Determine active voice mode and voice_id
        if self.rb_voice_id.isChecked():
            voice_mode = "manual"
            voice_id   = self.inp_voice_id.text().strip()
            voice_name = ""
        else:
            voice_mode = "list"
            voice_id   = self.cmb_voice.currentData() or ""
            voice_name = self.cmb_voice.currentText().split("  [")[0].strip() if voice_id else ""
        self.cfg.update({
            "provider":       self.cmb_provider.currentText(),
            "anthropic_key":  self.inp_anthropic_key.text().strip(),
            "gemini_key":     self.inp_gemini_key.text().strip(),
            "claude_model":   self.cmb_claude_model.currentText(),
            "gemini_model":   self.cmb_gemini_model.currentText(),
            "language":       self.cmb_language.currentText(),
            "video_theme":    self.cmb_video_theme.currentData() or "cream",
            "elevenlabs_key": self.inp_elevenlabs_key.text().strip(),
            "tts_provider":   "gemini" if self.rb_tts_google.isChecked() else "elevenlabs",
            "gemini_voice":   self.cmb_gemini_voice.currentText(),
            "tts_model":      self.cmb_tts_model.currentText(),
            "voice_mode":     voice_mode,
            "voice_id":       voice_id,
            "voice_name":     voice_name,
        })
        save_config(self.cfg)
        QMessageBox.information(self, "Đã lưu", "✅ Cấu hình đã được lưu thành công!\nCác API key và lựa chọn sẽ được nhớ cho lần sau.")

    # ──────────────────────────────────────────────
    # ElevenLabs voice loading
    # ──────────────────────────────────────────────
    def _get_active_voice_id(self):
        """Return (voice_id, display_name) based on current mode."""
        if self.rb_voice_list.isChecked():
            vid  = self.cmb_voice.currentData() or ""
            name = self.cmb_voice.currentText().split("  [")[0].strip() if vid else vid
        else:
            vid  = self.inp_voice_id.text().strip()
            name = vid
        return vid, name

    def _test_voice(self):
        key = self.inp_elevenlabs_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Thiếu API Key", "⚠️ Nhập ElevenLabs API Key trước.")
            return
        vid, name = self._get_active_voice_id()
        if not vid:
            QMessageBox.warning(self, "Chưa chọn giọng", "⚠️ Chọn giọng hoặc nhập Voice ID trước.")
            return
        model = self.cmb_tts_model.currentText()
        self.btn_test_voice.setEnabled(False)
        self.btn_test_voice.setText("⏳  Đang kiểm tra…")
        self._tv_thread = QThread()
        self._tv_worker = _TestVoiceWorker(key, vid, model)
        self._tv_worker.moveToThread(self._tv_thread)
        self._tv_thread.started.connect(self._tv_worker.run)
        self._tv_worker.success.connect(self._on_test_voice_ok)
        self._tv_worker.error.connect(self._on_test_voice_err)
        self._tv_thread.start()

    def _on_test_voice_ok(self, name):
        self.btn_test_voice.setEnabled(True)
        self.btn_test_voice.setText("🔍  Kiểm tra giọng (Test)")
        self._tv_thread.quit()
        QMessageBox.information(self, "Thành công ✅",
            f"✅ Giọng hoạt động tốt!\n\nVoice ID: {name}\nModel: {self.cmb_tts_model.currentText()}")

    def _on_test_voice_err(self, err):
        self.btn_test_voice.setEnabled(True)
        self.btn_test_voice.setText("🔍  Kiểm tra giọng (Test)")
        self._tv_thread.quit()
        QMessageBox.critical(self, "Lỗi giọng ❌", err)

    def _load_voices(self):
        key = self.inp_elevenlabs_key.text().strip()
        if not key:
            QMessageBox.warning(self, "Thiếu API Key", "⚠️ Vui lòng nhập ElevenLabs API Key trước.")
            return
        self.btn_load_voices.setEnabled(False)
        self.btn_load_voices.setText("⏳")
        # Run in background thread to not freeze UI
        t = QThread()
        self._voice_thread = t
        worker = _VoiceListWorker(key)
        self._voice_list_worker = worker
        worker.moveToThread(t)
        t.started.connect(worker.run)
        worker.finished.connect(self._on_voices_loaded)
        worker.error.connect(self._on_voices_error)
        t.start()

    def _on_voices_loaded(self, voices: list):
        """voices: list of (name, voice_id) tuples"""
        saved_id = self.cfg.get("voice_id", "")
        self.cmb_voice.blockSignals(True)
        self.cmb_voice.clear()
        restore_idx = 0
        for i, (name, vid) in enumerate(voices):
            self.cmb_voice.addItem(f"{name}  [{vid}]", userData=vid)
            if vid == saved_id:
                restore_idx = i
        self.cmb_voice.setCurrentIndex(restore_idx)
        self.cmb_voice.blockSignals(False)
        self._on_voice_selected(restore_idx)   # sync inp_voice_id
        self.btn_load_voices.setEnabled(True)
        self.btn_load_voices.setText("🔄  Tải giọng")
        self._voice_thread.quit()

    def _on_voices_error(self, err: str):
        self.btn_load_voices.setEnabled(True)
        self.btn_load_voices.setText("🔄  Tải giọng")
        QMessageBox.critical(self, "Lỗi tải giọng", f"❌ {err}")
        self._voice_thread.quit()

    def _on_voice_mode_changed(self, btn):
        """Enable/disable controls based on selected radio."""
        is_list = (self._voice_bg.id(btn) == 0)
        self.cmb_voice.setEnabled(is_list)
        self.btn_load_voices.setEnabled(is_list)
        self.inp_voice_id.setEnabled(not is_list)
        if is_list:
            self.inp_voice_id.setPlaceholderText("(tự điền khi chọn từ danh sách)")
        else:
            self.inp_voice_id.setPlaceholderText("Nhập Voice ID (vd: pNInz6obpgDQGcFmaJgB)")

    def _on_voice_selected(self, idx):
        """When a voice is picked from dropdown, just store internally (do NOT overwrite manual field)."""
        pass  # voice_id is read directly from cmb_voice.currentData() at save/use time

    # ──────────────────────────────────────────────
    # Generate actions
    # ──────────────────────────────────────────────
    def _do_generate(self):
        provider = self.cmb_provider.currentText()
        if provider == PROVIDER_GEMINI:
            key   = self.inp_gemini_key.text().strip()
            model = self.cmb_gemini_model.currentText()
            if not key:
                self.tabs.setCurrentIndex(0)
                QMessageBox.warning(self, "Thiếu API Key", "⚠️ Vui lòng nhập Gemini API Key ở tab Cài đặt trước.")
                return
        else:
            key   = self.inp_anthropic_key.text().strip()
            model = self.cmb_claude_model.currentText()
            if not key:
                self.tabs.setCurrentIndex(0)
                QMessageBox.warning(self, "Thiếu API Key", "⚠️ Vui lòng nhập Anthropic API Key ở tab Cài đặt trước.")
                return

        url_or_text = self.inp_url.text().strip() or self.txt_paste.toPlainText().strip()
        if not url_or_text:
            QMessageBox.warning(self, "Thiếu nội dung", "⚠️ Vui lòng nhập URL hoặc dán nội dung vào ô bên trên.")
            return

        mode = "promo" if self.cmb_mode.currentIndex() == 1 else "news"
        language = self.cmb_language.currentText()

        self.gen_log.clear()
        self.btn_gen.setEnabled(False)
        self.btn_gen.setText("⏳  Đang tạo…")

        duration_map = {
            0: (25, 32, 6),
            1: (55, 65, 10),
            2: (85, 95, 15),
            3: (115, 125, 20),
        }
        dur_idx = self.cmb_duration.currentIndex()
        dur_min, dur_max, n_scenes = duration_map.get(dur_idx, (25, 32, 6))

        self._gen_thread = QThread()
        self._gen_worker = GenerateWorker(key, mode, url_or_text, model, provider, language,
                                          dur_min=dur_min, dur_max=dur_max, n_scenes=n_scenes)
        self._gen_worker.moveToThread(self._gen_thread)
        self._gen_thread.started.connect(self._gen_worker.run)
        self._gen_worker.log.connect(lambda m: self.gen_log.appendPlainText(m))
        self._gen_worker.finished.connect(self._on_gen_done)
        self._gen_worker.error.connect(self._on_gen_error)
        self._gen_thread.start()

    def _on_gen_done(self, json_str):
        self.txt_json.setPlainText(json_str)
        self.btn_gen.setEnabled(True)
        self.btn_gen.setText("✨  Tạo Storyboard bằng AI")
        self._gen_thread.quit()
        self.gen_log.appendPlainText("✅ Storyboard sẵn sàng. Hãy xem xét và nhấn 'Lưu & Chuyển sang Render'.")

    def _on_gen_error(self, err):
        self.btn_gen.setEnabled(True)
        self.btn_gen.setText("✨  Tạo Storyboard bằng AI")
        self.gen_log.appendPlainText(f"❌ Lỗi: {err}")
        QMessageBox.critical(self, "Lỗi", f"Tạo storyboard thất bại:\n{err}")
        self._gen_thread.quit()

    def _load_json_file(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn Storyboard JSON", str(STORYBOARDS), "JSON (*.json)")
        if f:
            self.txt_json.setPlainText(pathlib.Path(f).read_text(encoding="utf-8"))

    def _save_json_and_switch(self):
        raw = self.txt_json.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "Trống", "⚠️ JSON storyboard đang trống.")
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON không hợp lệ", f"❌ Lỗi định dạng JSON:\n{e}")
            return

        slug = data.get("meta", {}).get("slug", "untitled")
        out_path = STORYBOARDS / f"{slug}.json"
        out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self._storyboard_path = str(out_path)
        self.lbl_storyboard.setText(str(out_path))
        self.tabs.setCurrentIndex(2)
        QMessageBox.information(self, "Đã lưu", f"✅ Storyboard đã lưu:\n{out_path}")

    # ──────────────────────────────────────────────
    # Render actions
    # ──────────────────────────────────────────────
    def _choose_storyboard(self):
        f, _ = QFileDialog.getOpenFileName(self, "Chọn Storyboard JSON", str(STORYBOARDS), "JSON (*.json)")
        if f:
            self._storyboard_path = f
            self.lbl_storyboard.setText(f)

    def _do_render(self):
        if not self._storyboard_path:
            QMessageBox.warning(self, "Chưa chọn", "⚠️ Hãy chọn hoặc lưu một storyboard trước.")
            return

        # Check at least one format selected
        formats = []
        if self.chk_16x9.isChecked(): formats.append("16x9")
        if self.chk_9x16.isChecked(): formats.append("9x16")
        if not formats:
            QMessageBox.warning(self, "Chưa chọn định dạng", "⚠️ Hãy chọn ít nhất một định dạng (16:9 hoặc 9:16).")
            return

        # Validate voice-over config if checked
        if self.chk_voiceover.isChecked():
            if self.rb_tts_google.isChecked():
                # Gemini TTS: needs Gemini API key
                if not self.inp_gemini_key.text().strip():
                    QMessageBox.warning(self, "Thiếu Gemini API Key",
                        "⚠️ Đã bật Voice-over (Gemini TTS) nhưng chưa nhập Gemini API Key.\n"
                        "Vui lòng vào tab ⚙️ Cài đặt → mục Gemini → nhập API Key.")
                    return
            else:
                # ElevenLabs
                key = self.inp_elevenlabs_key.text().strip()
                vid, _ = self._get_active_voice_id()
                if not key or not vid:
                    QMessageBox.warning(self, "Thiếu cấu hình ElevenLabs",
                        "⚠️ Đã bật Voice-over (ElevenLabs) nhưng chưa đủ cấu hình.\n"
                        "Vui lòng vào tab ⚙️ Cài đặt để nhập API Key và chọn giọng.\n\n"
                        "💡 Hoặc chuyển sang Gemini TTS (dùng chung API key Gemini).")
                    return

        self.render_log.clear()
        self.render_progress.setValue(0)
        self.lbl_out_16x9.setText("—")
        self.lbl_out_9x16.setText("—")
        self.lbl_vo_out.setText("—")
        self.btn_render.setEnabled(False)
        fmt_label = " & ".join(f.replace("x", ":") for f in formats)
        self.btn_render.setText(f"⏳  Đang render {fmt_label}…")

        self._ren_thread = QThread()
        video_theme = self.cmb_video_theme.currentData() or "cream"
        self._ren_worker = RenderWorker(self._storyboard_path, formats, video_theme=video_theme)
        self._ren_worker.moveToThread(self._ren_thread)
        self._ren_thread.started.connect(self._ren_worker.run)
        self._ren_worker.log.connect(lambda m: self.render_log.appendPlainText(m))
        self._ren_worker.progress.connect(self.render_progress.setValue)
        self._ren_worker.finished.connect(self._on_render_done)
        self._ren_worker.error.connect(self._on_render_error)
        self._ren_thread.start()

    def _on_render_done(self, p16, p9):
        self._video_16x9 = p16
        self._video_9x16 = p9
        self.lbl_out_16x9.setText(p16 or "—")
        self.lbl_out_9x16.setText(p9 or "—")
        self.btn_render.setEnabled(True)
        self.btn_render.setText("▶️  Bắt đầu Render")
        self._ren_thread.quit()

        # Auto chain voice-over if checked
        if self.chk_voiceover.isChecked():
            # Collect all rendered video paths
            vid_paths = [v for v in [p16, p9] if v]
            if vid_paths and self._storyboard_path:
                self.render_log.appendPlainText("\n🎙️ Bắt đầu tạo Voice-over…")
                self.btn_render.setEnabled(False)
                self.btn_render.setText("⏳  Đang tạo Voice-over…")
                self._voi_thread = QThread()

                use_gemini = self.rb_tts_google.isChecked()
                if use_gemini:
                    gemini_key   = self.inp_gemini_key.text().strip()
                    gemini_voice = self.cmb_gemini_voice.currentText()
                    self.render_log.appendPlainText(f"🤖 Gemini TTS — giọng: {gemini_voice} — {len(vid_paths)} video")
                    self._voi_worker = GeminiTTSWorker(
                        gemini_key, self._storyboard_path, vid_paths, gemini_voice
                    )
                else:
                    key      = self.inp_elevenlabs_key.text().strip()
                    voice_id, _ = self._get_active_voice_id()
                    tts_model   = self.cmb_tts_model.currentText()
                    # ElevenLabs: run on first video, second will be handled sequentially
                    self._voi_worker = VoiceWorker(key, voice_id, self._storyboard_path,
                                                   vid_paths[0], tts_model)

                self._voi_worker.moveToThread(self._voi_thread)
                self._voi_thread.started.connect(self._voi_worker.run)
                self._voi_worker.log.connect(lambda m: self.render_log.appendPlainText(m))
                self._voi_worker.finished.connect(self._on_vo_done)
                self._voi_worker.error.connect(self._on_vo_error)
                self._voi_thread.start()

        else:
            parts = []
            if p16: parts.append(f"16:9 → {p16}")
            if p9:  parts.append(f"9:16 → {p9}")
            QMessageBox.information(self, "Render xong! 🎉", "\n".join(parts))

    def _on_render_error(self, err):
        self.btn_render.setEnabled(True)
        self.btn_render.setText("▶️  Bắt đầu Render")
        self.render_log.appendPlainText(f"❌ Lỗi: {err}")
        QMessageBox.critical(self, "Lỗi Render", err)
        self._ren_thread.quit()

    def _on_vo_done(self, paths):
        # paths is a list of output files
        if isinstance(paths, str):
            paths = [paths]
        msg = "\n".join(f"✅ {p}" for p in paths)
        self.lbl_vo_out.setText("\n".join(paths))
        self.btn_render.setEnabled(True)
        self.btn_render.setText("▶️  Bắt đầu Render")
        self._voi_thread.quit()
        QMessageBox.information(self, "Hoàn thành! 🎉",
                                f"Video có tiếng ({len(paths)} file):\n{msg}")

    def _on_vo_error(self, err):
        self.btn_render.setEnabled(True)
        self.btn_render.setText("▶️  Bắt đầu Render")
        self.render_log.appendPlainText(f"❌ Voice-over lỗi: {err}")
        QMessageBox.critical(self, "Lỗi Voice-over", err)
        self._voi_thread.quit()

    def _open_output_dir(self):
        if sys.platform == "win32":
            os.startfile(str(OUTPUT_DIR))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(OUTPUT_DIR)])
        else:
            subprocess.Popen(["xdg-open", str(OUTPUT_DIR)])



# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AI Shorts Generator")
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
