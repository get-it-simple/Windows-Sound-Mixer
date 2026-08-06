Unicode true
ManifestDPIAware true
ManifestDPIAwareness PerMonitorV2

!ifndef APP_VERSION
  !error "APP_VERSION is required"
!endif
!ifndef APP_EXE
  !error "APP_EXE is required"
!endif
!ifndef INSTALL_SCOPE
  !error "INSTALL_SCOPE is required"
!endif
!ifndef OUTPUT_FILE
  !define OUTPUT_FILE "SoundMixer-${APP_VERSION}-${INSTALL_SCOPE}-setup.exe"
!endif

!define PRODUCT_ID "GetItSimple.SoundMixer"
!define PRODUCT_NAME "Sound Mixer"
!define PRODUCT_EXE "SoundMixer.exe"
!define PRODUCT_PUBLISHER "Get it Simple"
!define PRODUCT_URL "https://github.com/get-it-simple/Windows-Sound-Mixer"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_ID}"
!define DATA_DIR "$LOCALAPPDATA\GetItSimple\SoundMixer"

!if "${INSTALL_SCOPE}" == "machine"
  !define MACHINE_INSTALL
  !define REG_ROOT HKLM
  !define OTHER_REG_ROOT HKCU
  InstallDir "$PROGRAMFILES64\SoundMixer"
!else if "${INSTALL_SCOPE}" == "user"
  !define REG_ROOT HKCU
  !define OTHER_REG_ROOT HKLM
  InstallDir "$LOCALAPPDATA\Programs\SoundMixer"
!else
  !error "INSTALL_SCOPE must be user or machine"
!endif

RequestExecutionLevel user
Name "${PRODUCT_NAME}"
OutFile "${OUTPUT_FILE}"
BrandingText "${PRODUCT_PUBLISHER}"
InstallDirRegKey ${REG_ROOT} "${UNINSTALL_KEY}" "InstallLocation"
SetCompressor /SOLID zlib
CRCCheck force
XPStyle on
ShowInstDetails show
ShowUninstDetails show
VIProductVersion "${APP_VERSION}.0"
VIAddVersionKey /LANG=1033 "ProductName" "${PRODUCT_NAME}"
VIAddVersionKey /LANG=1033 "CompanyName" "${PRODUCT_PUBLISHER}"
VIAddVersionKey /LANG=1033 "FileDescription" "${PRODUCT_NAME} Installer"
VIAddVersionKey /LANG=1033 "FileVersion" "${APP_VERSION}.0"
VIAddVersionKey /LANG=1033 "ProductVersion" "${APP_VERSION}"
VIAddVersionKey /LANG=1033 "LegalCopyright" "Copyright (c) 2026 ${PRODUCT_PUBLISHER}"

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "WinVer.nsh"
!include "x64.nsh"
!include "nsDialogs.nsh"
!include "theme.nsh"

!define MUI_ICON "..\resources\icons\app.ico"
!define MUI_UNICON "..\resources\icons\app.ico"
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "$(LaunchText)"
!define MUI_FINISHPAGE_RUN_FUNCTION FinishRun
!define MUI_PAGE_CUSTOMFUNCTION_SHOW ApplySystemTheme
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipForProgressMode
!insertmacro MUI_PAGE_WELCOME
Page custom LicensePageCreate LicensePageLeave
!define MUI_PAGE_CUSTOMFUNCTION_SHOW ApplySystemTheme
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipForProgressMode
!insertmacro MUI_PAGE_DIRECTORY
!define MUI_PAGE_CUSTOMFUNCTION_SHOW ApplySystemTheme
!insertmacro MUI_PAGE_INSTFILES
!define MUI_PAGE_CUSTOMFUNCTION_SHOW FinishPageShow
!define MUI_PAGE_CUSTOMFUNCTION_PRE SkipForProgressMode
!insertmacro MUI_PAGE_FINISH

UninstPage custom un.PurgePageCreate un.PurgePageLeave
!define MUI_PAGE_CUSTOMFUNCTION_SHOW un.ApplySystemTheme
!insertmacro MUI_UNPAGE_INSTFILES
!define MUI_PAGE_CUSTOMFUNCTION_SHOW un.ApplySystemTheme
!insertmacro MUI_UNPAGE_FINISH

!insertmacro MUI_LANGUAGE "English"
!insertmacro MUI_LANGUAGE "Ukrainian"

LangString LaunchText ${LANG_ENGLISH} "Launch Sound Mixer"
LangString LaunchText ${LANG_UKRAINIAN} "Запустити Sound Mixer"
LangString LicenseTitle ${LANG_ENGLISH} "License Agreement"
LangString LicenseTitle ${LANG_UKRAINIAN} "Ліцензійна угода"
LangString LicenseSubtitle ${LANG_ENGLISH} "Review the license terms before installing Sound Mixer."
LangString LicenseSubtitle ${LANG_UKRAINIAN} "Ознайомтеся з умовами ліцензійної угоди перед встановленням Sound Mixer."
LangString LicenseTop ${LANG_ENGLISH} "Press Page Down to review the rest of the agreement."
LangString LicenseTop ${LANG_UKRAINIAN} "Натисніть Page Down, щоб переглянути угоду далі."
LangString LicenseBottom ${LANG_ENGLISH} "Click I Agree to accept the agreement and continue installation."
LangString LicenseBottom ${LANG_UKRAINIAN} "Натисніть «Погоджуюся», щоб прийняти угоду та продовжити встановлення."
LangString LicenseAgree ${LANG_ENGLISH} "I Agree"
LangString LicenseAgree ${LANG_UKRAINIAN} "Погоджуюся"
LangString MachineExists ${LANG_ENGLISH} "A machine-wide installation already exists. Uninstall it before installing the user version."
LangString MachineExists ${LANG_UKRAINIAN} "Системну версію вже встановлено. Видаліть її перед встановленням версії для користувача."
LangString UnsupportedWindows ${LANG_ENGLISH} "Sound Mixer requires 64-bit Windows 10 version 1809 or newer."
LangString UnsupportedWindows ${LANG_UKRAINIAN} "Sound Mixer потребує 64-бітну Windows 10 версії 1809 або новішу."
LangString OtherSessionRunning ${LANG_ENGLISH} "Sound Mixer is running in another Windows session. Close it there before continuing."
LangString OtherSessionRunning ${LANG_UKRAINIAN} "Sound Mixer працює в іншому сеансі Windows. Закрийте його там перед продовженням."
LangString StopFailed ${LANG_ENGLISH} "The running Sound Mixer process could not be stopped."
LangString StopFailed ${LANG_UKRAINIAN} "Не вдалося зупинити запущений процес Sound Mixer."
LangString OldUninstallFailed ${LANG_ENGLISH} "The previous version could not be removed. Installation was not changed."
LangString OldUninstallFailed ${LANG_UKRAINIAN} "Не вдалося видалити попередню версію. Встановлення не змінено."
LangString InstallFailed ${LANG_ENGLISH} "Sound Mixer could not be installed."
LangString InstallFailed ${LANG_UKRAINIAN} "Не вдалося встановити Sound Mixer."
LangString PurgeTitle ${LANG_ENGLISH} "Application data"
LangString PurgeTitle ${LANG_UKRAINIAN} "Дані застосунку"
LangString PurgeText ${LANG_ENGLISH} "Delete settings for the current Windows user"
LangString PurgeText ${LANG_UKRAINIAN} "Видалити налаштування поточного користувача Windows"
LangString UninstallTitle ${LANG_ENGLISH} "Uninstall Sound Mixer"
LangString UninstallTitle ${LANG_UKRAINIAN} "Видалення Sound Mixer"
LangString UninstallSubtitle ${LANG_ENGLISH} "Remove Sound Mixer from your computer."
LangString UninstallSubtitle ${LANG_UKRAINIAN} "Видалення Sound Mixer з комп'ютера."
LangString UninstallPrompt ${LANG_ENGLISH} "Sound Mixer will be removed from:$\r$\n$INSTDIR"
LangString UninstallPrompt ${LANG_UKRAINIAN} "Sound Mixer буде видалено з:$\r$\n$INSTDIR"
LangString UninstallButton ${LANG_ENGLISH} "Uninstall"
LangString UninstallButton ${LANG_UKRAINIAN} "Видалити"
LangString UninstallFailed ${LANG_ENGLISH} "Sound Mixer could not be uninstalled."
LangString UninstallFailed ${LANG_UKRAINIAN} "Не вдалося видалити Sound Mixer."

Var WasRunning
Var WasRunningBeforeInstall
Var ExistingDir
Var ExistingUninstaller
Var ElevatedPhase
Var PurgeData
Var PurgeCheckbox
Var UninstallNext
Var SilentProgress
Var ProcessStatus
Var ProcessTarget
Var LicenseEdit
Var LicenseNext
!ifdef MACHINE_INSTALL
Var UserInstallDir
Var UserUninstaller
!endif

Function CheckWindows
  ${IfNot} ${RunningX64}
    MessageBox MB_OK|MB_ICONSTOP "$(UnsupportedWindows)" /SD IDOK
    SetErrorLevel 4
    Quit
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_OK|MB_ICONSTOP "$(UnsupportedWindows)" /SD IDOK
    SetErrorLevel 4
    Quit
  ${EndIf}
  ReadRegStr $0 HKLM "Software\Microsoft\Windows NT\CurrentVersion" "CurrentBuildNumber"
  IntCmp $0 17763 supported unsupported supported
unsupported:
  MessageBox MB_OK|MB_ICONSTOP "$(UnsupportedWindows)" /SD IDOK
  SetErrorLevel 4
  Quit
supported:
FunctionEnd

Function SkipForProgressMode
  StrCmp $SilentProgress 1 0 show
  Abort
show:
FunctionEnd

Function LicensePageCreate
  StrCmp $SilentProgress 1 0 show
  Abort
show:
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}

  !insertmacro MUI_HEADER_TEXT "$(LicenseTitle)" "$(LicenseSubtitle)"
  ${NSD_CreateLabel} 0 0 100% 12u "$(LicenseTop)"
  Pop $0

  nsDialogs::CreateControl EDIT ${DEFAULT_STYLES}|${WS_TABSTOP}|${WS_VSCROLL}|${ES_MULTILINE}|${ES_READONLY}|${ES_AUTOVSCROLL}|${ES_WANTRETURN} ${WS_EX_CLIENTEDGE} 0 16u 100% -42u ""
  Pop $LicenseEdit

  ${NSD_CreateLabel} 0 -22u 100% 22u "$(LicenseBottom)"
  Pop $0

  InitPluginsDir
  Push $OUTDIR
  SetOutPath "$PLUGINSDIR"
  File /oname=SoundMixer-License.txt "..\LICENSE"
  Pop $OUTDIR
  FileOpen $0 "$PLUGINSDIR\SoundMixer-License.txt" r
license_read:
  ClearErrors
  FileRead $0 $1
  IfErrors license_done
  StrCpy $1 "$1$\r$\n"
  SendMessage $LicenseEdit ${EM_SETSEL} -1 -1
  SendMessage $LicenseEdit ${EM_REPLACESEL} 0 "STR:$1"
  Goto license_read
license_done:
  FileClose $0
  SendMessage $LicenseEdit ${EM_SETSEL} 0 0

  GetDlgItem $LicenseNext $HWNDPARENT 1
  SendMessage $LicenseNext ${WM_SETTEXT} 0 "STR:$(LicenseAgree)"
  Call ApplySystemTheme
  nsDialogs::Show
FunctionEnd

Function LicensePageLeave
  SendMessage $LicenseNext ${WM_SETTEXT} 0 "STR:$(^NextBtn)"
FunctionEnd

Function DetectAndStopApplication
  StrCpy $WasRunning 0
  StrCmp $ExistingDir "" done
  IfFileExists "$ExistingDir\${PRODUCT_EXE}" 0 done
  StrCpy $ProcessTarget "$ExistingDir\${PRODUCT_EXE}"
  Call InspectExactProcess
  StrCmp $ProcessStatus 3 other_session
  StrCmp $ProcessStatus 1 0 done
  StrCpy $WasRunning 1
  nsExec::Exec '"$ExistingDir\${PRODUCT_EXE}" --shutdown-for-update'
  StrCpy $9 50
wait_for_exit:
  Sleep 100
  Call InspectExactProcess
  StrCmp $ProcessStatus 0 done
  StrCmp $ProcessStatus 3 other_session
  IntOp $9 $9 - 1
  IntCmp $9 0 force_stop wait_for_exit wait_for_exit
force_stop:
  Call TerminateExactProcess
  Sleep 200
  Call InspectExactProcess
  StrCmp $ProcessStatus 0 done
  StrCmp $ProcessStatus 3 other_session
  MessageBox MB_OK|MB_ICONSTOP "$(StopFailed)" /SD IDOK
  SetErrorLevel 2
  Quit
other_session:
  MessageBox MB_OK|MB_ICONSTOP "$(OtherSessionRunning)" /SD IDOK
  SetErrorLevel 2
  Quit
done:
FunctionEnd

!ifdef MACHINE_INSTALL
Function RunElevatedInstaller
  ; The bootstrap owns all UI. The elevated child only changes machine files
  ; and registry, so the finish page can launch the app unelevated.
  StrCpy $0 "/S /ELEVATED /D=$INSTDIR"
  System::Call 'kernel32::SetEnvironmentVariableW(w "SM_INSTALLER", w "$EXEPATH") i.r1'
  System::Call 'kernel32::SetEnvironmentVariableW(w "SM_ARGUMENTS", w "$0") i.r1'
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "$$p=Start-Process -FilePath $$env:SM_INSTALLER -ArgumentList $$env:SM_ARGUMENTS -Verb RunAs -Wait -PassThru; exit $$p.ExitCode"'
  Pop $1
  Pop $2
  StrCmp $1 "error" 0 +2
  StrCpy $1 4
  StrCpy $0 $1
  StrCmp $0 0 0 done
  Call RemovePreviousUserVersion
done:
FunctionEnd
!endif

Function .onInit
  System::Call 'kernel32::GetUserDefaultUILanguage() i.r0'
  StrCpy $LANGUAGE ${LANG_ENGLISH}
  IntCmp $0 ${LANG_UKRAINIAN} 0 +2 +2
  StrCpy $LANGUAGE ${LANG_UKRAINIAN}
  SetRegView 64
  Call CheckWindows
  StrCpy $WasRunning 0
  StrCpy $WasRunningBeforeInstall 0
  StrCpy $ElevatedPhase 0
  StrCpy $SilentProgress 0
  !ifdef MACHINE_INSTALL
    StrCpy $UserInstallDir ""
    StrCpy $UserUninstaller ""
  !endif
  ClearErrors
  ${GetOptions} $CMDLINE "/SILENTWITHPROGRESS" $0
  IfErrors check_elevation
  StrCpy $SilentProgress 1
  SetAutoClose true
check_elevation:
  ClearErrors
  ${GetOptions} $CMDLINE "/ELEVATED" $0
  IfErrors not_elevated elevated
not_elevated:
  !ifndef MACHINE_INSTALL
    ReadRegStr $0 HKLM "${UNINSTALL_KEY}" "InstallLocation"
    StrCmp $0 "" 0 machine_exists
  !endif
  Goto done
elevated:
  StrCpy $ElevatedPhase 1
  UserInfo::GetAccountType
  Pop $0
  StrCmp $0 "Admin" 0 admin_required
  Goto done
!ifndef MACHINE_INSTALL
machine_exists:
  MessageBox MB_OK|MB_ICONSTOP "$(MachineExists)" /SD IDOK
  SetErrorLevel 5
  Quit
!endif
admin_required:
  MessageBox MB_OK|MB_ICONSTOP "Administrator rights are required." /SD IDOK
  SetErrorLevel 4
  Quit
done:
FunctionEnd

Function MigrateLegacySettings
  IfFileExists "${DATA_DIR}\settings.json" done
  IfFileExists "$ExistingDir\settings.json" 0 done
  CreateDirectory "${DATA_DIR}"
  Delete "${DATA_DIR}\settings.json.migrating"
  CopyFiles /SILENT "$ExistingDir\settings.json" "${DATA_DIR}\settings.json.migrating"
  IfFileExists "${DATA_DIR}\settings.json" cleanup
  Rename "${DATA_DIR}\settings.json.migrating" "${DATA_DIR}\settings.json"
cleanup:
  Delete "${DATA_DIR}\settings.json.migrating"
done:
FunctionEnd

Function RemovePreviousVersion
  ReadRegStr $ExistingUninstaller ${REG_ROOT} "${UNINSTALL_KEY}" "UninstallString"
  ReadRegStr $ExistingDir ${REG_ROOT} "${UNINSTALL_KEY}" "InstallLocation"
  StrCmp $ExistingUninstaller "" done
  !ifndef MACHINE_INSTALL
  Call MigrateLegacySettings
  !endif
  !ifdef MACHINE_INSTALL
    ExecWait '$ExistingUninstaller /S /UPGRADE /ELEVATED _?=$ExistingDir' $0
  !else
  ExecWait '$ExistingUninstaller /S /UPGRADE _?=$ExistingDir' $0
  !endif
  StrCmp $0 0 done
  MessageBox MB_OK|MB_ICONSTOP "$(OldUninstallFailed)" /SD IDOK
  SetErrorLevel 3
  Abort
done:
FunctionEnd

!ifdef MACHINE_INSTALL
Function RemovePreviousUserVersion
  StrCmp $UserUninstaller "" done
  ExecWait '$UserUninstaller /S /UPGRADE _?=$UserInstallDir' $0
  StrCmp $0 0 done
  MessageBox MB_OK|MB_ICONSTOP "$(OldUninstallFailed)" /SD IDOK
  SetErrorLevel 3
  Quit
done:
FunctionEnd
!endif

Function RememberRunningState
  StrCmp $WasRunning 1 0 done
  StrCpy $WasRunningBeforeInstall 1
done:
FunctionEnd

Function FinishPageShow
  Call ApplySystemTheme
  ; An upgrade never restores the old running state automatically. The user
  ; can still explicitly select the launch option on this page.
  StrCmp $WasRunningBeforeInstall 1 0 done
  ${NSD_Uncheck} $mui.FinishPage.Run
done:
FunctionEnd

Function FinishRun
  Exec '"$INSTDIR\${PRODUCT_EXE}"'
FunctionEnd

Section "Install"
  StrCpy $WasRunningBeforeInstall 0
  !ifdef MACHINE_INSTALL
    StrCmp $ElevatedPhase 1 machine_file_phase

    ; Stop installed copies only after the user starts the install phase.
    ; Both checks run in the interactive user's session before UAC elevation.
    SetShellVarContext current
    ReadRegStr $ExistingDir HKLM "${UNINSTALL_KEY}" "InstallLocation"
    StrCmp $ExistingDir "" check_user_install
    Call DetectAndStopApplication
    Call RememberRunningState
    Call MigrateLegacySettings

check_user_install:
    ReadRegStr $UserInstallDir HKCU "${UNINSTALL_KEY}" "InstallLocation"
    ReadRegStr $UserUninstaller HKCU "${UNINSTALL_KEY}" "UninstallString"
    StrCmp $UserInstallDir "" run_elevated_install
    StrCpy $ExistingDir $UserInstallDir
    Call DetectAndStopApplication
    Call RememberRunningState
    Call MigrateLegacySettings

run_elevated_install:
    Call RunElevatedInstaller
    StrCmp $0 0 machine_bootstrap_done
    MessageBox MB_OK|MB_ICONSTOP "$(InstallFailed)" /SD IDOK
    SetErrorLevel $0
    Abort

machine_bootstrap_done:
    Goto install_done

machine_file_phase:
    SetShellVarContext all
  !else
    SetShellVarContext current
    ReadRegStr $ExistingDir HKCU "${UNINSTALL_KEY}" "InstallLocation"
    StrCmp $ExistingDir "" user_install_files
    Call DetectAndStopApplication
    Call RememberRunningState

user_install_files:
  !endif
  Call RemovePreviousVersion
  SetOutPath "$INSTDIR"
  File /oname=${PRODUCT_EXE} "${APP_EXE}"
  FileOpen $0 "$INSTDIR\.sound-mixer-installed" w
  FileWrite $0 "installed"
  FileClose $0
  File /oname=LICENSE "..\LICENSE"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateDirectory "$SMPROGRAMS\Sound Mixer"
  CreateShortcut "$SMPROGRAMS\Sound Mixer\Sound Mixer.lnk" "$INSTDIR\${PRODUCT_EXE}"
  CreateShortcut "$SMPROGRAMS\Sound Mixer\Uninstall Sound Mixer.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "Publisher" "${PRODUCT_PUBLISHER}"
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${PRODUCT_EXE}"
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "URLInfoAbout" "${PRODUCT_URL}"
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "HelpLink" "${PRODUCT_URL}/issues"
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "URLUpdateInfo" "${PRODUCT_URL}/releases"
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "QuietUninstallString" "$\"$INSTDIR\Uninstall.exe$\" /S"
  WriteRegDWORD ${REG_ROOT} "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD ${REG_ROOT} "${UNINSTALL_KEY}" "NoRepair" 1
  ${GetTime} "" "L" $0 $1 $2 $3 $4 $5 $6
  WriteRegStr ${REG_ROOT} "${UNINSTALL_KEY}" "InstallDate" "$2$1$0"
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  WriteRegDWORD ${REG_ROOT} "${UNINSTALL_KEY}" "EstimatedSize" $0
  !ifdef MACHINE_INSTALL
install_done:
  !endif
SectionEnd

Function un.StopApplication
  StrCpy $ExistingDir "$INSTDIR"
  Call un.DetectAndStopApplication
FunctionEnd

Function un.DetectAndStopApplication
  StrCpy $WasRunning 0
  IfFileExists "$ExistingDir\${PRODUCT_EXE}" 0 done
  StrCpy $ProcessTarget "$ExistingDir\${PRODUCT_EXE}"
  Call un.InspectExactProcess
  StrCmp $ProcessStatus 3 other_session
  StrCmp $ProcessStatus 1 0 done
  StrCpy $WasRunning 1
  nsExec::Exec '"$ExistingDir\${PRODUCT_EXE}" --shutdown-for-update'
  StrCpy $9 50
wait_for_exit:
  Sleep 100
  Call un.InspectExactProcess
  StrCmp $ProcessStatus 0 done
  StrCmp $ProcessStatus 3 other_session
  IntOp $9 $9 - 1
  IntCmp $9 0 force_stop wait_for_exit wait_for_exit
force_stop:
  Call un.TerminateExactProcess
  Sleep 200
  Call un.InspectExactProcess
  StrCmp $ProcessStatus 0 done
  StrCmp $ProcessStatus 3 other_session
  MessageBox MB_OK|MB_ICONSTOP "$(StopFailed)" /SD IDOK
  SetErrorLevel 2
  Quit
other_session:
  MessageBox MB_OK|MB_ICONSTOP "$(OtherSessionRunning)" /SD IDOK
  SetErrorLevel 2
  Quit
done:
FunctionEnd

!ifdef MACHINE_INSTALL
Function un.RunElevated
  StrCpy $0 "/S /ELEVATED"
  System::Call 'kernel32::SetEnvironmentVariableW(w "SM_INSTALLER", w "$EXEPATH") i.r1'
  System::Call 'kernel32::SetEnvironmentVariableW(w "SM_ARGUMENTS", w "$0") i.r1'
  nsExec::ExecToStack '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "$$p=Start-Process -FilePath $$env:SM_INSTALLER -ArgumentList $$env:SM_ARGUMENTS -Verb RunAs -Wait -PassThru; exit $$p.ExitCode"'
  Pop $1
  Pop $2
  StrCmp $1 "error" 0 +2
  StrCpy $1 4
  StrCpy $0 $1
FunctionEnd
!endif

Function un.onInit
  System::Call 'kernel32::GetUserDefaultUILanguage() i.r0'
  StrCpy $LANGUAGE ${LANG_ENGLISH}
  IntCmp $0 ${LANG_UKRAINIAN} 0 +2 +2
  StrCpy $LANGUAGE ${LANG_UKRAINIAN}
  SetRegView 64
  StrCpy $ElevatedPhase 0
  !ifdef MACHINE_INSTALL
    ReadRegStr $1 HKLM "${UNINSTALL_KEY}" "InstallLocation"
    StrCmp $1 "" +2
    StrCpy $INSTDIR $1
  !endif
  StrCpy $PurgeData 0
  ClearErrors
  ${GetOptions} $CMDLINE "/PURGE" $0
  IfErrors elevation
  StrCpy $PurgeData 1
elevation:
  !ifdef MACHINE_INSTALL
    ClearErrors
    ${GetOptions} $CMDLINE "/ELEVATED" $0
    IfErrors done elevated
elevated:
    StrCpy $ElevatedPhase 1
    UserInfo::GetAccountType
    Pop $0
    StrCmp $0 "Admin" done
    SetErrorLevel 4
    Quit
  !endif
  !ifdef MACHINE_INSTALL
done:
  !endif
FunctionEnd

Function un.PurgePageCreate
  IfSilent done
  nsDialogs::Create 1018
  Pop $0
  ${If} $0 == error
    Abort
  ${EndIf}
  !insertmacro MUI_HEADER_TEXT "$(UninstallTitle)" "$(UninstallSubtitle)"
  ${NSD_CreateLabel} 0 0 100% 34u "$(UninstallPrompt)"
  Pop $0
  ${NSD_CreateLabel} 0 48u 100% 18u "$(PurgeTitle)"
  Pop $0
  ${NSD_CreateCheckbox} 0 72u 100% 24u "$(PurgeText)"
  Pop $PurgeCheckbox
  ${NSD_Uncheck} $PurgeCheckbox
  GetDlgItem $UninstallNext $HWNDPARENT 1
  SendMessage $UninstallNext ${WM_SETTEXT} 0 "STR:$(UninstallButton)"
  Call un.ApplySystemTheme
  nsDialogs::Show
done:
FunctionEnd

Function un.PurgePageLeave
  IfSilent done
  ${NSD_GetState} $PurgeCheckbox $0
  StrCmp $0 ${BST_CHECKED} 0 restore_button
  StrCpy $PurgeData 1
restore_button:
  SendMessage $UninstallNext ${WM_SETTEXT} 0 "STR:$(^NextBtn)"
done:
FunctionEnd

Function un.PurgeCurrentUserData
  Delete "${DATA_DIR}\settings.json"
  Delete "${DATA_DIR}\settings.json.bak"
  Delete "${DATA_DIR}\settings.json.tmp"
  RMDir "${DATA_DIR}"
  RMDir "$LOCALAPPDATA\GetItSimple"
FunctionEnd

Section "Uninstall"
  !ifdef MACHINE_INSTALL
    StrCmp $ElevatedPhase 1 machine_files
    Call un.StopApplication
    StrCmp $PurgeData 1 0 +2
    Call un.PurgeCurrentUserData
    Call un.RunElevated
    StrCmp $0 0 done
    MessageBox MB_OK|MB_ICONSTOP "$(UninstallFailed)" /SD IDOK
    SetErrorLevel $0
    Abort
machine_files:
    SetShellVarContext all
    Goto remove_files
  !else
    Call un.StopApplication
    SetShellVarContext current
  !endif
  !ifdef MACHINE_INSTALL
remove_files:
  !endif
  Delete "$SMPROGRAMS\Sound Mixer\Sound Mixer.lnk"
  Delete "$SMPROGRAMS\Sound Mixer\Uninstall Sound Mixer.lnk"
  RMDir "$SMPROGRAMS\Sound Mixer"
  DeleteRegKey ${REG_ROOT} "${UNINSTALL_KEY}"
  Delete "$INSTDIR\${PRODUCT_EXE}"
  Delete "$INSTDIR\.sound-mixer-installed"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  !ifndef MACHINE_INSTALL
  StrCmp $PurgeData 1 0 done
  Call un.PurgeCurrentUserData
  !endif
done:
SectionEnd

!include "process_control.nsh"
