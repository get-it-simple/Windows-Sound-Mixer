!macro DefineElevationFunction UN
Function ${UN}ElevateAndWait
  StrCpy $ElevationExitCode 4
  System::Call '*(i 60, i 0x140, p $HWNDPARENT, w "runas", w "$EXEPATH", w "$ElevateArguments", p 0, i 1, p 0, p 0, p 0, p 0, i 0, p 0, p .r2) p.r1'
  System::Call 'shell32::ShellExecuteExW(p r1) i.r3'
  StrCmp $3 0 shell_failed
  System::Call '*$1(i, i, p, p, p, p, p, i, p, p, p, p, i, p, p .r2)'
  StrCmp $2 0 cleanup
  System::Call 'kernel32::WaitForSingleObject(p r2, i 0xFFFFFFFF) i.r3'
  StrCmp $3 0xFFFFFFFF close_process
  System::Call 'kernel32::GetExitCodeProcess(p r2, *i .r3) i.r4'
  StrCmp $4 0 close_process
  StrCpy $ElevationExitCode $3
close_process:
  System::Call 'kernel32::CloseHandle(p r2)'
  Goto cleanup
shell_failed:
  System::Call 'kernel32::GetLastError() i.r3'
  StrCmp $3 1223 0 cleanup
  StrCpy $ElevationExitCode 1223
cleanup:
  System::Free $1
FunctionEnd
!macroend

!ifdef MACHINE_INSTALL
  !insertmacro DefineElevationFunction ""
  !insertmacro DefineElevationFunction "un."
!endif
