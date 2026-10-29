; Cytellect per-user Windows installer (Inno Setup 6). Built only by
; scripts/build_windows_installer.py, which passes the defines below and a payload
; whose every file is hash-listed. No administrator rights, commands or choices.

#ifndef AppVersion
  #error AppVersion is required (scripts/build_windows_installer.py)
#endif
#ifndef NumericVersion
  #error NumericVersion is required
#endif
#ifndef PayloadDir
  #error PayloadDir is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif
#ifndef RequiredInstallMB
  #error RequiredInstallMB is required
#endif
#ifndef RequiredUpdateMB
  #error RequiredUpdateMB is required
#endif
#ifndef PayloadMB
  #error PayloadMB is required
#endif

[Setup]
; Never change AppId: Windows "Apps" and updates identify Cytellect by it.
AppId={{6F1E0A2C-4C1B-4E57-9B2D-3C7A1F0E9D21}
AppName=Cytellect
AppVersion={#AppVersion}
AppVerName=Cytellect {#AppVersion}
AppPublisher=Cytellect
AppPublisherURL=https://cytellect.app/
AppSupportURL=https://github.com/genellect/cytellect
VersionInfoVersion={#NumericVersion}
VersionInfoProductName=Cytellect
VersionInfoDescription=Cytellect セットアップ
; Per-user installation: no administrator rights and no destination choice (I2).
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Cytellect
DisableDirPage=yes
UsePreviousAppDir=no
DisableProgramGroupPage=yes
DisableWelcomePage=yes
DisableReadyPage=no
ArchitecturesAllowed=x64os
ArchitecturesInstallIn64BitMode=x64os
MinVersion=10.0.17763
; The uninstaller lives beside, never inside, the research data folder.
UninstallFilesDir={app}\uninstall
UninstallDisplayName=Cytellect
UninstallDisplayIcon={app}\uninstall\unins000.exe
SetupMutex=CytellectSetupMutex
CloseApplications=no
RestartApplications=no
WizardStyle=modern
ShowLanguageDialog=no
; Bundled archives (Fiji, Python, wheels) are already compressed.
Compression=lzma2/normal
SolidCompression=no
OutputDir={#OutputDir}
OutputBaseFilename=Cytellect-Setup-{#AppVersion}
#ifdef SignToolName
; Code-signing hook (owner decision D4). ISCC receives /S{#SignToolName}=<command>.
SignTool={#SignToolName}
SignedUninstaller=yes
#endif

[Languages]
Name: "ja"; MessagesFile: "compiler:Languages\Japanese.isl"

[Messages]
SetupAppTitle=Cytellect セットアップ
SetupWindowTitle=Cytellect セットアップ
ReadyLabel1=Cytellect をこの PC にインストールします。
ReadyLabel2b=「インストール」を押すと始まります。管理者権限・コマンド入力・設定の変更は必要ありません。

[CustomMessages]
ReadyMemoDestination=インストール先（変更不要）:
ReadyMemoSpace=必要な空き容量: 約 %1 GB（Python・解析ライブラリ・Fiji を同梱しています。インターネット接続は不要です）
ReadyMemoTime=所要時間: 約 5〜10 分
PreflightOs=この Windows には対応していません。Windows 10（バージョン 1809 以降）または Windows 11 の 64 ビット版（x64）が必要です。%n%n何も変更せずに終了します。
PreflightArchitecture=この PC のプロセッサーには対応していません。x64（Intel・AMD）の 64 ビット版 Windows が必要です。ARM 版 Windows には対応していません。%n%n何も変更せずに終了します。
PreflightMemory=メモリーが不足しています。8 GB 以上のメモリーが必要です（この PC: 約 %1 MB）。%n%n何も変更せずに終了します。
PreflightDisk=インストール先のドライブの空き容量が不足しています。あと約 %1 MB の空きが必要です（必要: 約 %2 MB、空き: 約 %3 MB）。%n%n不要なファイルを削除して空きを作ってから、もう一度このインストーラーを開いてください。何も変更していません。
PreflightTemp=一時フォルダーのドライブの空き容量が不足しています。あと約 %1 MB の空きが必要です。%n%n空きを作ってから、もう一度このインストーラーを開いてください。何も変更していません。
PreflightPowerShell=インストールに必要な Windows PowerShell を起動できませんでした。何も変更していません。%n%nPC を再起動してから、もう一度このインストーラーを開いてください。それでも続く場合は、組織の設定で PowerShell が止められている可能性があるため、PC の管理者にご相談ください。
RootNotOwned=インストール先「%1」に、Cytellect 以外のファイルがあります。既存のファイルを守るため、何も変更せずに終了します。%n%nそのフォルダーの中身が不要か、別の場所に移せるものであれば、移してからもう一度このインストーラーを開いてください。判断できない場合は、PC の管理者にご相談ください。
PreparingWorkspace=Cytellect を準備しています（約 5〜10 分）。このまま閉じずにお待ちください…
Phase_verify_release=配布ファイルを確認しています…
Phase_download_uv=セットアップツールを準備しています…
Phase_download_python=Python を準備しています…
Phase_install_python=Python を準備しています…
Phase_install_dependencies=解析ライブラリを準備しています…
Phase_verify_python_gui=起動・停止の画面を確認しています…
Phase_install_fiji=Fiji を準備しています（数分かかります）…
Phase_verify_fiji=Fiji のプラグインとモデルを確認しています…
Phase_check_analysis=検出と計算を確認しています…
Phase_create_shortcut=ショートカットを作成しています…
Phase_complete=仕上げをしています…
Phase_manage_storage=仕上げをしています…
FinishedHeading=インストールが完了しました
FinishedText=作業画面をブラウザで開きました。%n%n開かない場合は、デスクトップの「Cytellect」を開き、表示される小さな画面の「作業画面を開く」を押してください。研究データはこの PC の中だけに保存されます。
FailedHeading=インストールを完了できませんでした
FailedText=%1%n%n次の順に試してください。%n1. もう一度このインストーラーを開く（準備済みの部分は再利用され、続きから再開します）%n2. PC を再起動してから、もう一度開く%n3. インストーラーをダウンロードし直して開く%nそれでも続く場合は、下の詳細を添えて PC の管理者にご相談ください。%n%n詳細: %2 / %3
FailedGeneric=準備の途中で止まりました。
FailedApplicationControl=Windows の保護機能（Smart App Control など）が、Cytellect の一部の実行を止めました。セキュリティ設定は変えないでください。%n%nCytellect の公式サイトからインストーラーをダウンロードし直して開いても止まる場合は、この PC では今の配布物を使えません。PC の管理者に配布物の確認を依頼してください。
FailedNotOwned=インストール先に Cytellect 以外のファイルがあります。
FailedPayload=インストーラーのファイルが壊れているか、一部が欠けています。ダウンロードし直してから開いてください。
AlreadyRunning=この版の Cytellect はインストール済みで、起動しています。作業画面をブラウザで開きます。%n%n開かない場合は、起動・停止の画面の「作業画面を開く」を押してください。
UninstallRunning=Cytellect が起動しています。起動・停止の画面で「停止して閉じる」を押してから、もう一度アンインストールしてください。
UninstallAskData=研究データ（作業データ・結果・設定）も削除しますか？%n%n「いいえ」を選ぶと、データは次の場所に残ります。もう一度インストールすると引き継がれます。%n%1%n%n「はい」を選ぶと、削除したデータは元に戻せません。

[Files]
Source: "preflight.ps1"; Flags: dontcopy
Source: "{#PayloadDir}\release\*"; DestDir: "{tmp}\payload\release"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#PayloadDir}\offline\*"; DestDir: "{tmp}\payload\offline"; Flags: ignoreversion recursesubdirs createallsubdirs nocompression
; Licenses of the bundled software and where its source is published (docs/oss.md).
Source: "{#PayloadDir}\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion recursesubdirs createallsubdirs

[Code]
const
  UninstallKey = 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{6F1E0A2C-4C1B-4E57-9B2D-3C7A1F0E9D21}_is1';
  ShortcutDescription = 'Cytellect local analysis and control window';
  LauncherMutex = 'CytellectLocalLauncher';

var
  PreviousVersion: String;
  HadPreviousVersion: Boolean;
  SetupFailed: Boolean;
  FailurePhase: String;
  FailureCode: String;
  StatusPath: String;
  StatusTimer: LongWord;
  DeleteResearchData: Boolean;

function SetTimer(hWnd: LongWord; nIDEvent, uElapse: LongWord; lpTimerFunc: LongWord): LongWord;
  external 'SetTimer@user32.dll stdcall';
function KillTimer(hWnd: LongWord; uIDEvent: LongWord): LongWord;
  external 'KillTimer@user32.dll stdcall';

function PowerShellPath(): String;
begin
  Result := ExpandConstant('{sysnative}\WindowsPowerShell\v1.0\powershell.exe');
end;

function ReadValue(const Lines: TArrayOfString; const Key: String): String;
var
  I: Integer;
begin
  Result := '';
  for I := 0 to GetArrayLength(Lines) - 1 do
    if Pos(Key + '=', Lines[I]) = 1 then
      Result := Trim(Copy(Lines[I], Length(Key) + 2, Length(Lines[I])));
end;

function DirectoryIsEmpty(const Path: String): Boolean;
var
  FindRec: TFindRec;
begin
  Result := True;
  if FindFirst(AddBackslash(Path) + '*', FindRec) then
  try
    repeat
      if (FindRec.Name <> '.') and (FindRec.Name <> '..') then
      begin
        Result := False;
        Exit;
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;

function RootOwned(const Root: String): Boolean;
var
  Marker: AnsiString;
begin
  // Same rule as scripts/local_setup.ps1: only an empty folder or our own marker.
  Result := (not DirExists(Root)) or DirectoryIsEmpty(Root);
  if (not Result) and LoadStringFromFile(AddBackslash(Root) + 'setup-root.json', Marker) then
    Result := Pos('"cytellect-local"', String(Marker)) > 0;
end;

function SameVersionInstalled(const Root: String): Boolean;
var
  FindRec: TFindRec;
begin
  Result := False;
  if FindFirst(AddBackslash(Root) + 'apps\{#AppVersion}-*', FindRec) then
  try
    repeat
      if FileExists(AddBackslash(Root) + 'apps\' + FindRec.Name + '\setup-complete.json') then
        Result := True;
    until Result or not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
end;

function InitializeSetup(): Boolean;
var
  Root: String;
  ResultCode: Integer;
begin
  HadPreviousVersion := RegQueryStringValue(HKCU, UninstallKey, 'DisplayVersion', PreviousVersion);
  SetupFailed := False;
  Result := True;
  Root := RemoveQuotes(ExpandConstant('{param:DIR|}'));
  if Root = '' then
    Root := ExpandConstant('{localappdata}\Cytellect');
  // This version is installed and open: say so and open its workspace (I5). A silent
  // re-run continues instead; setup reuses everything without touching the running copy.
  if (not WizardSilent) and CheckForMutexes(LauncherMutex) and SameVersionInstalled(Root) then
  begin
    MsgBox(CustomMessage('AlreadyRunning'), mbInformation, MB_OK);
    ShellExec('open', 'http://127.0.0.1:8765/', '', '', SW_SHOWNORMAL, ewNoWait, ResultCode);
    Result := False;
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo,
  MemoComponentsInfo, MemoGroupInfo, MemoTasksInfo: String): String;
begin
  Result := CustomMessage('ReadyMemoDestination') + NewLine + Space + WizardDirValue + NewLine + NewLine +
    FmtMessage(CustomMessage('ReadyMemoSpace'), [IntToStr(({#RequiredInstallMB} + {#PayloadMB} + 1023) div 1024)]) +
    NewLine + NewLine + CustomMessage('ReadyMemoTime');
end;

function PreflightMessage(const Lines: TArrayOfString): String;
var
  Code: String;
  RequiredMB, FreeMB: Integer;
begin
  Result := '';
  Code := ReadValue(Lines, 'code');
  RequiredMB := StrToIntDef(ReadValue(Lines, 'required_mb'), 0);
  FreeMB := StrToIntDef(ReadValue(Lines, 'free_mb'), 0);
  if Code = 'os_unsupported' then
    Result := CustomMessage('PreflightOs')
  else if Code = 'architecture_unsupported' then
    Result := CustomMessage('PreflightArchitecture')
  else if Code = 'memory_insufficient' then
    Result := FmtMessage(CustomMessage('PreflightMemory'), [ReadValue(Lines, 'memory_mb')])
  else if Code = 'disk_insufficient' then
    Result := FmtMessage(CustomMessage('PreflightDisk'), [IntToStr(RequiredMB - FreeMB), IntToStr(RequiredMB), IntToStr(FreeMB)])
  else if Code = 'temp_insufficient' then
    Result := FmtMessage(CustomMessage('PreflightTemp'), [IntToStr(RequiredMB - FreeMB)]);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Root, Script, ResultFile: String;
  Lines: TArrayOfString;
  ResultCode: Integer;
begin
  // Every check here is read-only: a refusal leaves the PC unchanged (I4).
  Result := '';
  Root := RemoveBackslashUnlessRoot(WizardDirValue);
  if not RootOwned(Root) then
  begin
    Result := FmtMessage(CustomMessage('RootNotOwned'), [Root]);
    Exit;
  end;
  ExtractTemporaryFile('preflight.ps1');
  Script := ExpandConstant('{tmp}\preflight.ps1');
  ResultFile := ExpandConstant('{tmp}\preflight-result.txt');
  if not Exec(PowerShellPath(), '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + Script +
    '" -InstallRoot "' + Root + '" -TempRoot "' + ExpandConstant('{tmp}') +
    '" -RequiredInstallMB {#RequiredInstallMB} -RequiredUpdateMB {#RequiredUpdateMB} -PayloadMB {#PayloadMB}' +
    ' -ResultFile "' + ResultFile + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) or
    not LoadStringsFromFile(ResultFile, Lines) then
  begin
    Result := CustomMessage('PreflightPowerShell');
    Exit;
  end;
  // check_failed (a measurement error) does not block; setup verifies the platform again.
  Result := PreflightMessage(Lines);
end;

procedure WriteRootMarker();
var
  Root: String;
begin
  Root := ExpandConstant('{app}');
  ForceDirectories(Root);
  // Claim an empty destination before Inno Setup writes its uninstaller into it.
  if not FileExists(AddBackslash(Root) + 'setup-root.json') then
    SaveStringToFile(AddBackslash(Root) + 'setup-root.json', '{"product":"cytellect-local","schema":1}', False);
end;

procedure ShowPhase();
var
  Phase: AnsiString;
  Name: String;
begin
  if not LoadStringFromFile(StatusPath, Phase) then
    Exit;
  Name := Trim(String(Phase));
  if (Name = '') or (Pos(' ', Name) > 0) then
    Exit;
  try
    WizardForm.StatusLabel.Caption := CustomMessage('Phase_' + Name);
  except
    WizardForm.StatusLabel.Caption := CustomMessage('PreparingWorkspace');
  end;
end;

procedure OnStatusTimer(Wnd: LongWord; Msg: LongWord; TimerId: LongWord; Time: LongWord);
begin
  ShowPhase();
end;

function FailureText(): String;
var
  Reason: String;
begin
  if FailureCode = 'windows_application_control_blocked' then
    Reason := CustomMessage('FailedApplicationControl')
  else if FailureCode = 'install_directory_not_owned' then
    Reason := CustomMessage('FailedNotOwned')
  else if (Pos('offline', FailureCode) = 1) or (Pos('release', FailureCode) = 1) or
    (FailureCode = 'invalid_release_manifest') then
    Reason := CustomMessage('FailedPayload')
  else
    Reason := CustomMessage('FailedGeneric');
  Result := FmtMessage(CustomMessage('FailedText'), [Reason, FailurePhase, FailureCode]);
end;

procedure RunCytellectSetup();
var
  Payload, ResultFile, Params: String;
  Outcome: AnsiString;
  Words: String;
  ResultCode, Space: Integer;
begin
  Payload := ExpandConstant('{tmp}\payload');
  StatusPath := ExpandConstant('{tmp}\setup-status.txt');
  ResultFile := ExpandConstant('{tmp}\setup-result.txt');
  DeleteFile(ResultFile);
  WizardForm.StatusLabel.Caption := CustomMessage('PreparingWorkspace');
  WizardForm.FilenameLabel.Caption := '';
  WizardForm.ProgressGauge.Style := npbstMarquee;
  WizardForm.CancelButton.Enabled := False;
  Params := '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + Payload + '\release\scripts\local_setup.ps1"' +
    ' -SourceRoot "' + Payload + '\release" -InstallRoot "' + ExpandConstant('{app}') + '"' +
    ' -OfflineRoot "' + Payload + '\offline" -Console' +
    ' -StatusFile "' + StatusPath + '" -ResultFile "' + ResultFile + '"';
  StatusTimer := SetTimer(0, 0, 500, CreateCallback(@OnStatusTimer));
  try
    if not Exec(PowerShellPath(), Params, Payload + '\release', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      ResultCode := -1;
  finally
    KillTimer(0, StatusTimer);
    WizardForm.ProgressGauge.Style := npbstNormal;
  end;
  if (ResultCode = 0) and LoadStringFromFile(ResultFile, Outcome) and (Trim(String(Outcome)) = 'ok') then
    Exit;
  SetupFailed := True;
  FailurePhase := 'setup';
  FailureCode := 'setup_failed';
  if LoadStringFromFile(ResultFile, Outcome) then
  begin
    // "failed <phase> <code>", fixed ASCII written by local_setup.ps1.
    Words := Trim(String(Outcome));
    if Pos('failed ', Words) = 1 then
    begin
      Words := Copy(Words, 8, Length(Words));
      Space := Pos(' ', Words);
      if Space > 0 then
      begin
        FailurePhase := Copy(Words, 1, Space - 1);
        FailureCode := Copy(Words, Space + 1, Length(Words));
      end;
    end;
  end;
  // An update that did not finish keeps the previous version; keep its listing too.
  if HadPreviousVersion then
    RegWriteStringValue(HKCU, UninstallKey, 'DisplayVersion', PreviousVersion);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
    WriteRootMarker()
  else if CurStep = ssPostInstall then
  begin
    RunCytellectSetup();
    // Open the workspace right away. Silent installs (CI, in-app updates) never launch.
    if (not SetupFailed) and (not WizardSilent) then
      ShellExec('', ExpandConstant('{userprograms}\Cytellect.lnk'), '', '', SW_SHOWNORMAL, ewNoWait, ResultCode);
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpFinished then
  begin
    if SetupFailed then
    begin
      WizardForm.FinishedHeadingLabel.Caption := CustomMessage('FailedHeading');
      WizardForm.FinishedLabel.Caption := FailureText();
    end
    else
    begin
      WizardForm.FinishedHeadingLabel.Caption := CustomMessage('FinishedHeading');
      WizardForm.FinishedLabel.Caption := CustomMessage('FinishedText');
    end;
  end;
end;

function GetCustomSetupExitCode(): Integer;
begin
  // Callers (CI, the in-app update) see an unfinished setup as a failure.
  if SetupFailed then
    Result := 20
  else
    Result := 0;
end;

function HasParameter(const Name: String): Boolean;
var
  I: Integer;
begin
  Result := False;
  for I := 1 to ParamCount do
    if CompareText(ParamStr(I), Name) = 0 then
      Result := True;
end;

procedure RemoveOwnedShortcut(const Path: String);
var
  Shell, Link: Variant;
  Target, Description, Apps: String;
begin
  if not FileExists(Path) then
    Exit;
  Apps := Lowercase(AddBackslash(ExpandConstant('{app}')) + 'apps\');
  try
    Shell := CreateOleObject('WScript.Shell');
    Link := Shell.CreateShortcut(Path);
    // Read the OLE properties into strings before comparing them.
    Target := Link.TargetPath;
    Target := Lowercase(Target);
    Description := Link.Description;
    // Remove only the stable shortcut that this installation created.
    if (Description = ShortcutDescription) and (Pos(Apps, Target) = 1) then
      DeleteFile(Path);
  except
  end;
end;

function KeptWithData(const Name: String): Boolean;
begin
  Result := (CompareText(Name, 'data') = 0) or (CompareText(Name, 'settings') = 0) or
    (CompareText(Name, 'setup-root.json') = 0) or (CompareText(Name, 'uninstall') = 0);
end;

procedure RemoveInstallation(const Root: String; KeepData: Boolean);
var
  FindRec: TFindRec;
  Names: TArrayOfString;
  I, Count: Integer;
begin
  Count := 0;
  if FindFirst(AddBackslash(Root) + '*', FindRec) then
  try
    repeat
      if (FindRec.Name <> '.') and (FindRec.Name <> '..') and
        (CompareText(FindRec.Name, 'uninstall') <> 0) and not (KeepData and KeptWithData(FindRec.Name)) then
      begin
        SetArrayLength(Names, Count + 1);
        Names[Count] := FindRec.Name;
        Count := Count + 1;
      end;
    until not FindNext(FindRec);
  finally
    FindClose(FindRec);
  end;
  for I := 0 to Count - 1 do
    if DirExists(AddBackslash(Root) + Names[I]) then
      DelTree(AddBackslash(Root) + Names[I], True, True, True)
    else
      DeleteFile(AddBackslash(Root) + Names[I]);
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  // The launcher holds this mutex while it runs; never remove a running installation.
  if CheckForMutexes(LauncherMutex) then
  begin
    SuppressibleMsgBox(CustomMessage('UninstallRunning'), mbError, MB_OK, IDOK);
    Result := False;
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  Root: String;
begin
  if CurUninstallStep = usUninstall then
  begin
    Root := ExpandConstant('{app}');
    // Research data stays unless the researcher explicitly chooses deletion (I8).
    DeleteResearchData := HasParameter('/DELETEDATA') or
      (SuppressibleMsgBox(FmtMessage(CustomMessage('UninstallAskData'), [AddBackslash(Root) + 'data']),
        mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES);
    RemoveOwnedShortcut(ExpandConstant('{userdesktop}\Cytellect.lnk'));
    RemoveOwnedShortcut(ExpandConstant('{userprograms}\Cytellect.lnk'));
    RemoveInstallation(Root, not DeleteResearchData);
  end;
end;
