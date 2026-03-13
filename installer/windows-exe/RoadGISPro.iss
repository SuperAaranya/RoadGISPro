#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "work\\payload"
#endif
#ifndef OutputDir
  #define OutputDir "out"
#endif

[Setup]
AppId={{7F3E0A35-6EDB-45E4-BD6B-D78C3A1AF6E9}
AppName=RoadGISPro
AppVersion={#MyAppVersion}
AppPublisher=RoadGISPro
DefaultDirName={autopf}\RoadGISPro
DefaultGroupName=RoadGISPro
DisableDirPage=no
DisableProgramGroupPage=yes
OutputDir={#OutputDir}
OutputBaseFilename=RoadGISProSetup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Types]
Name: "full"; Description: "Full installation"
Name: "compact"; Description: "Core only"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "core"; Description: "RoadGISPro core application"; Types: full compact custom; Flags: fixed
Name: "lang_go"; Description: "Go language tools"; Types: full custom
Name: "lang_rust"; Description: "Rust language tools"; Types: full custom
Name: "lang_js"; Description: "JavaScript language tools"; Types: full custom
Name: "lang_ruby"; Description: "Ruby language tools"; Types: full custom
Name: "lang_java"; Description: "Java language tools"; Types: full custom
Name: "lang_csharp"; Description: "C# language tools"; Types: full custom

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "{#SourceDir}\components\core\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: core
Source: "{#SourceDir}\components\go\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".placeholder"; Components: lang_go
Source: "{#SourceDir}\components\rust\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".placeholder"; Components: lang_rust
Source: "{#SourceDir}\components\js\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".placeholder"; Components: lang_js
Source: "{#SourceDir}\components\ruby\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".placeholder"; Components: lang_ruby
Source: "{#SourceDir}\components\java\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".placeholder"; Components: lang_java
Source: "{#SourceDir}\components\csharp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: ".placeholder"; Components: lang_csharp

[Icons]
Name: "{autoprograms}\RoadGISPro"; Filename: "{app}\RoadGISPro.exe"
Name: "{autodesktop}\RoadGISPro"; Filename: "{app}\RoadGISPro.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\RoadGISPro.exe"; Description: "Launch RoadGISPro"; Flags: nowait postinstall skipifsilent
