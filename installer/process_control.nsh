!macro DefineProcessControlFunctions UN
Function ${UN}InspectExactProcess
  StrCpy $ProcessStatus 0
  System::Call 'kernel32::GetCurrentProcessId() i.r0'
  System::Call 'kernel32::ProcessIdToSessionId(i r0, *i .r1) i.r0'
  System::Call 'kernel32::CreateToolhelp32Snapshot(i 0x2, i 0) p.r2'
  StrCmp $2 -1 done
  System::Call '*(&l4, i, i, p, i, i, i, i, i, &t260) p.r3'
  System::Call 'kernel32::Process32FirstW(p r2, p r3) i.r4'
loop:
  StrCmp $4 0 cleanup
  System::Call '*$3(i, i, i .r5, p, i, i, i, i, i, &t260 .r6)'
  System::Call 'kernel32::lstrcmpiW(w r6, w "${PRODUCT_EXE}") i.r7'
  StrCmp $7 0 0 next
  System::Call 'kernel32::OpenProcess(i 0x1000, i 0, i r5) p.r7'
  StrCmp $7 0 next
  System::Alloc 4
  Pop $8
  System::Call '*$8(i ${NSIS_MAX_STRLEN})'
  System::StrAlloc ${NSIS_MAX_STRLEN}
  Pop $R0
  System::Call 'kernel32::QueryFullProcessImageNameW(p r7, i 0, p R0, p r8) i.r4'
  StrCmp $4 0 close_process
  System::Call '*$R0(&t${NSIS_MAX_STRLEN} .R1)'
  System::Call 'kernel32::lstrcmpiW(w R1, w "$ProcessTarget") i.r4'
  StrCmp $4 0 0 close_process
  System::Call 'kernel32::ProcessIdToSessionId(i r5, *i .r4) i.r6'
  StrCmp $6 0 close_process
  StrCmp $4 $1 same_session
  StrCpy $ProcessStatus 3
  Goto close_process
same_session:
  StrCmp $ProcessStatus 3 close_process
  StrCpy $ProcessStatus 1
close_process:
  System::Free $R0
  System::Free $8
  System::Call 'kernel32::CloseHandle(p r7)'
next:
  System::Call 'kernel32::Process32NextW(p r2, p r3) i.r4'
  Goto loop
cleanup:
  System::Free $3
  System::Call 'kernel32::CloseHandle(p r2)'
done:
FunctionEnd

Function ${UN}TerminateExactProcess
  StrCpy $ProcessStatus 0
  System::Call 'kernel32::GetCurrentProcessId() i.r0'
  System::Call 'kernel32::ProcessIdToSessionId(i r0, *i .r1) i.r0'
  System::Call 'kernel32::CreateToolhelp32Snapshot(i 0x2, i 0) p.r2'
  StrCmp $2 -1 done
  System::Call '*(&l4, i, i, p, i, i, i, i, i, &t260) p.r3'
  System::Call 'kernel32::Process32FirstW(p r2, p r3) i.r4'
loop:
  StrCmp $4 0 cleanup
  System::Call '*$3(i, i, i .r5, p, i, i, i, i, i, &t260 .r6)'
  System::Call 'kernel32::lstrcmpiW(w r6, w "${PRODUCT_EXE}") i.r7'
  StrCmp $7 0 0 next
  System::Call 'kernel32::OpenProcess(i 0x1001, i 0, i r5) p.r7'
  StrCmp $7 0 next
  System::Alloc 4
  Pop $8
  System::Call '*$8(i ${NSIS_MAX_STRLEN})'
  System::StrAlloc ${NSIS_MAX_STRLEN}
  Pop $R0
  System::Call 'kernel32::QueryFullProcessImageNameW(p r7, i 0, p R0, p r8) i.r4'
  StrCmp $4 0 close_process
  System::Call '*$R0(&t${NSIS_MAX_STRLEN} .R1)'
  System::Call 'kernel32::lstrcmpiW(w R1, w "$ProcessTarget") i.r4'
  StrCmp $4 0 0 close_process
  System::Call 'kernel32::ProcessIdToSessionId(i r5, *i .r4) i.r6'
  StrCmp $6 0 close_process
  StrCmp $4 $1 same_session
  StrCpy $ProcessStatus 3
  Goto close_process
same_session:
  StrCmp $ProcessStatus 3 close_process
  System::Call 'kernel32::TerminateProcess(p r7, i 2) i.r4'
  StrCmp $4 0 close_process
  StrCpy $ProcessStatus 1
close_process:
  System::Free $R0
  System::Free $8
  System::Call 'kernel32::CloseHandle(p r7)'
next:
  System::Call 'kernel32::Process32NextW(p r2, p r3) i.r4'
  Goto loop
cleanup:
  System::Free $3
  System::Call 'kernel32::CloseHandle(p r2)'
done:
FunctionEnd
!macroend

!insertmacro DefineProcessControlFunctions ""
!insertmacro DefineProcessControlFunctions "un."
