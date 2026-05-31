; ════════════════════════════════════════════════════════════════════
;  AI Shorts Generator — Inno Setup Script  (Inno Setup 6.x)
;
;  Bộ cài HOÀN TOÀN STANDALONE:
;    - Không cần cài Python
;    - Không cần cài Node.js
;    - Không cần cài ffmpeg
;    - Không cần internet sau khi cài
;
;  Yêu cầu TRƯỚC KHI build bộ cài này:
;    Chạy build_nuitka.bat để tạo:
;      dist\AIShorts.exe
;      node_portable\        (Node.js 20 portable)
;      playwright-browsers\  (Chromium đã tải sẵn)
;      node_modules\         (Playwright npm package)
; ════════════════════════════════════════════════════════════════════

#define AppName        "AI Shorts Generator"
#define AppVersion     "1.0.0"
#define AppPublisher   "AI Shorts Generator"
#define AppExeName     "AIShorts.exe"

; Thư mục source (cùng cấp với file .iss này)
#define SrcDir   ".\"
#define DistDir  ".\dist"

[Setup]
; ── Định danh ─────────────────────────────────────────────────────
AppId={{A3F2C8D1-9E4B-4F07-B3C6-1D2E5F8A0B9C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}

; ── Đường dẫn cài đặt ────────────────────────────────────────────
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes

; ── Output ───────────────────────────────────────────────────────
OutputDir={#SrcDir}installer_output
OutputBaseFilename=AIShorts-Setup-v{#AppVersion}
SetupIconFile={#SrcDir}logo.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}

; ── Nén (LZMA ultra cho file nhỏ nhất) ──────────────────────────
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4

; ── Giao diện ─────────────────────────────────────────────────────
WizardStyle=modern
WizardResizable=no
DisableWelcomePage=no
DisableDirPage=no
DisableProgramGroupPage=yes
ShowLanguageDialog=no

; ── Quyền & yêu cầu hệ thống ─────────────────────────────────────
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

; ── Khởi động lại ────────────────────────────────────────────────
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo icon trên Desktop"; GroupDescription: "Tùy chọn:"; Flags: unchecked

[Files]
; ── Ứng dụng chính (Nuitka onefile) ─────────────────────────────
Source: "{#DistDir}\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; ── Icon ─────────────────────────────────────────────────────────
Source: "{#SrcDir}logo.ico"; DestDir: "{app}"; Flags: ignoreversion

; ── Engine (render.html) ─────────────────────────────────────────
Source: "{#SrcDir}engine\*"; DestDir: "{app}\engine"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Tests (Playwright spec) ──────────────────────────────────────
Source: "{#SrcDir}tests\*"; DestDir: "{app}\tests"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

; ── Playwright config + package.json ─────────────────────────────
Source: "{#SrcDir}package.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}package-lock.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SrcDir}playwright.config.ts"; DestDir: "{app}"; Flags: ignoreversion

; ── Node.js portable (runtime tự chứa) ──────────────────────────
Source: "{#SrcDir}node_portable\*"; DestDir: "{app}\node_portable"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── node_modules (Playwright npm package) ────────────────────────
Source: "{#SrcDir}node_modules\*"; DestDir: "{app}\node_modules"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── Playwright Chromium browser (tải sẵn) ────────────────────────
Source: "{#SrcDir}playwright-browsers\*"; DestDir: "{app}\playwright-browsers"; Flags: ignoreversion recursesubdirs createallsubdirs

; ── FFmpeg (bundled) ─────────────────────────────────────────────
Source: "{#SrcDir}ffmpeg\*"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
; Tạo sẵn thư mục cần thiết
Name: "{app}\storyboards"
Name: "{app}\output"

[Icons]
; Start Menu
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\logo.ico"
Name: "{group}\Gỡ cài đặt {#AppName}"; Filename: "{uninstallexe}"

; Desktop (tùy chọn)
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\logo.ico"; Tasks: desktopicon

[Run]
; Mở app sau khi cài xong
Filename: "{app}\{#AppExeName}"; Description: "Khởi động {#AppName} ngay bây giờ"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Dọn sạch khi gỡ cài
Type: filesandordirs; Name: "{app}\storyboards"
Type: filesandordirs; Name: "{app}\output"
Type: filesandordirs; Name: "{app}\__pycache__"
