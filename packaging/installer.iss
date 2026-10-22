; Inno Setup script for G4UniversalSim (roadmap D). Built by packaging/build_package.py:
;   ISCC /DAppVersion=1.0.0 /DSourceDir=<portable package folder> /DOutputDir=<out> /DOutputName=<name> installer.iss
; Installs the portable package folder unchanged, adds Start-menu shortcuts and an
; uninstaller, and asks for the existing Geant4 data folder, which it writes into
; {app}\bin\geant4-data.txt (the Geant4 data itself is not installed).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #error SourceDir (the portable package folder) is required
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
#ifndef OutputName
  #define OutputName "G4UniversalSim-setup"
#endif

[Setup]
AppId={{6C1F4E2B-8A57-4B0D-9C3E-5D2A7F1B9E44}
AppName=G4UniversalSim
AppVersion={#AppVersion}
AppPublisher=G4UniversalSim
DefaultDirName={autopf}\G4UniversalSim
DefaultGroupName=G4UniversalSim
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename={#OutputName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=G4UniversalSim {#AppVersion}
UninstallDisplayIcon={app}\gui\G4UniversalSimGUI.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\G4UniversalSim"; Filename: "{app}\gui\G4UniversalSimGUI.exe"; WorkingDir: "{app}"
Name: "{group}\G4UniversalSim documentation"; Filename: "{app}\docs"
Name: "{group}\Read me"; Filename: "{app}\README-package.md"
Name: "{group}\Uninstall G4UniversalSim"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\gui\G4UniversalSimGUI.exe"; Description: "Start G4UniversalSim"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\bin\geant4-data.txt"

[Code]
var
  DataPage: TInputDirWizardPage;

function GuessDataDir(): String;
begin
  Result := GetEnv('GEANT4_DATA_DIR');
  if (Result = '') and (GetEnv('G4LEDATA') <> '') then
    Result := ExtractFileDir(GetEnv('G4LEDATA'));
end;

procedure InitializeWizard();
begin
  DataPage := CreateInputDirPage(wpSelectDir, 'Geant4 data folder',
    'Where are the Geant4 11.3 datasets?',
    'G4UniversalSim does not install the Geant4 physics data (about 3 GB). Choose the folder that ' +
    'contains G4EMLOW8.6.1, PhotonEvaporation6.1, RadioactiveDecay6.1.2, G4PARTICLEXS4.1 and ' +
    'G4ENSDFSTATE3.0 (for example <Geant4 install>\share\Geant4\data). Leave it empty if GEANT4_DATA_DIR ' +
    'or the G4...DATA variables are already set; you can change it later in bin\geant4-data.txt.',
    False, '');
  DataPage.Add('');
  DataPage.Values[0] := GuessDataDir();
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = DataPage.ID) and (DataPage.Values[0] <> '') and
     not DirExists(AddBackslash(DataPage.Values[0]) + 'G4EMLOW8.6.1') then
    Result := MsgBox('G4EMLOW8.6.1 was not found in this folder. Use it anyway?', mbConfirmation, MB_YESNO) = IDYES;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  FileName: String;
begin
  if (CurStep = ssPostInstall) and (DataPage.Values[0] <> '') then
  begin
    FileName := ExpandConstant('{app}\bin\geant4-data.txt');
    SaveStringToFile(FileName, DataPage.Values[0] + #13#10, True);
  end;
end;
