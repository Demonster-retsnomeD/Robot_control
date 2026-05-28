[Setup]
AppName=Robot Control
AppVersion=1.0
AppPublisher=ATT System
DefaultDirName={autopf}\RobotControl
DefaultGroupName=Robot Control
OutputDir=dist
OutputBaseFilename=RobotControl_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=
PrivilegesRequired=lowest

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "Create desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
Source: "dist\RobotControl\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\Robot Control"; Filename: "{app}\RobotControl.exe"
Name: "{group}\Uninstall Robot Control"; Filename: "{uninstallexe}"
Name: "{commondesktop}\Robot Control"; Filename: "{app}\RobotControl.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\RobotControl.exe"; Description: "Launch Robot Control"; Flags: nowait postinstall skipifsilent
