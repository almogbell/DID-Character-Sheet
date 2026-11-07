#define MyAppName "DID Character Sheet"
#define MyAppVersion "1.0.14"
#define MyAppPublisher "DID"
#define MyAppExeName "DID Character Sheet.exe"

[Setup]
; IMPORTANT: Never change this AppId between releases.
AppId={{0DCE3792-7789-4AE5-B5A7-18AB2A512928}

AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}

DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest

OutputDir=installer_output
OutputBaseFilename=DID_Character_Sheet_Setup_{#MyAppVersion}

Compression=lzma2
SolidCompression=yes
WizardStyle=modern

UsePreviousAppDir=yes
CloseApplications=no
RestartApplications=no

UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}

; Use the fantasy DID image for the installer itself.
SetupIconFile=app_icon.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\DID Character Sheet.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "suggestions_config.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
