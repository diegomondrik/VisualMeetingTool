; Inno Setup's recipe for VisualMeetingTool-Setup-<version>.exe (WI18), run by
; packaging/build.py, which passes Version and Source (PyInstaller's folder).
;
; - It asks first in which language it is to be read; the Name of each language
;   is the application's code for it (meetingtool.texts.LANGUAGES), and the one
;   chosen is written to installation.ini next to the program: the installed
;   application starts in it (meetingtool.app.window.installed_language).
; - For the current user only, without administrator rights.
; - The data folder is the user's, outside the program: nothing here touches it.

#ifndef Version
  #error Version is passed by packaging/build.py
#endif
#ifndef Source
  #error Source is passed by packaging/build.py
#endif

[Setup]
; The same AppId for every version: a new one installs over the old one.
AppId={{6B7C2E3A-9D41-4F0E-8A57-3C1E5D2B9F84}
AppName=VisualMeetingTool
AppVersion={#Version}
AppVerName=VisualMeetingTool {#Version}
AppPublisher=Carlos Diego Mondrik
AppPublisherURL=https://github.com/diegomondrik/VisualMeetingTool
DefaultDirName={autopf}\VisualMeetingTool
DefaultGroupName=VisualMeetingTool
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
ShowLanguageDialog=yes
UsePreviousLanguage=no
CloseApplications=yes
UninstallDisplayIcon={app}\MeetingTool.exe
UninstallDisplayName=VisualMeetingTool
OutputBaseFilename=VisualMeetingTool-Setup-{#Version}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#Source}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[INI]
Filename: "{app}\installation.ini"; Section: "installation"; Key: "language"; String: "{language}"; Flags: uninsdeletesection

[Icons]
Name: "{autoprograms}\VisualMeetingTool"; Filename: "{app}\MeetingTool.exe"
Name: "{autodesktop}\VisualMeetingTool"; Filename: "{app}\MeetingTool.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MeetingTool.exe"; Description: "{cm:LaunchProgram,VisualMeetingTool}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\installation.ini"
