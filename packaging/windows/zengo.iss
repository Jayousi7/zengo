; Zengo's Windows installer (Inno Setup 6). Built by the release CI:
;   iscc /DVersion=1.0.0 /DSource=..\..\dist\zengo.exe packaging\windows\zengo.iss
; Installs for the current user only (no admin rights needed), with a Start-menu
; entry, an optional desktop icon and start at login, and an uninstaller.

#ifndef Version
  #define Version "0.0.0"
#endif
#ifndef Source
  #define Source "..\..\dist\zengo.exe"
#endif

[Setup]
AppId={{6A1E3C2B-7F4D-4E8A-9B1C-2D5E8F0A3C71}
AppName=Zengo
AppVersion={#Version}
AppVerName=Zengo {#Version}
AppPublisher=Zengo
AppPublisherURL=https://github.com/Jayousi7/zengo
DefaultDirName={autopf}\Zengo
DefaultGroupName=Zengo
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=zengo-{#Version}-setup
SetupIconFile=..\icons\zengo.ico
UninstallDisplayIcon={app}\zengo.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Put Zengo on the desktop"; Flags: unchecked
Name: "startatlogin"; Description: "Start Zengo when I log in"

[Files]
Source: "{#Source}"; DestDir: "{app}"; DestName: "zengo.exe"; Flags: ignoreversion

[Icons]
Name: "{group}\Zengo"; Filename: "{app}\zengo.exe"
Name: "{group}\Uninstall Zengo"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Zengo"; Filename: "{app}\zengo.exe"; Tasks: desktopicon

[Registry]
; The same value his own "Start at login" setting uses, so the two agree.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Zengo"; ValueData: """{app}\zengo.exe"""; Tasks: startatlogin; Flags: uninsdeletevalue

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM zengo.exe /F"; Flags: runhidden; RunOnceId: "StopZengo"

[Code]
// Remove the start-at-login value even if it was set from his settings rather
// than by this installer. (What he remembers, in %APPDATA%\Zengo, is kept.)
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Zengo');
end;

[Run]
Filename: "{app}\zengo.exe"; Description: "Start Zengo now"; Flags: nowait postinstall skipifsilent
