Function VerifyExistingUninstallerSignature
  StrCpy $SignatureStatus 2
  System::Call '*(&i4 0x00AAC56B, &i2 0xCD44, &i2 0x11D0, &i1 0x8C, &i1 0xC2, &i1 0x00, &i1 0xC0, &i1 0x4F, &i1 0xC2, &i1 0x95, &i1 0xEE) p.r0'
  System::Call '*(i 16, w "$ExistingUninstaller", p 0, p 0) p.r1'
  System::Call '*(i 52, p 0, p 0, i 2, i 0, i 1, p r1, i 0, p 0, p 0, i 0x10, i 0, p 0) p.r2'
  System::Call 'wintrust::WinVerifyTrust(p -1, p r0, p r2) i.r3'
  StrCmp $3 0 signature_valid
  IntCmpU $3 0x800B0100 no_signature check_provider check_provider
check_provider:
  IntCmpU $3 0x800B0001 no_signature check_subject check_subject
check_subject:
  IntCmpU $3 0x800B0003 no_signature cleanup cleanup
signature_valid:
  StrCpy $SignatureStatus 0
  Goto cleanup
no_signature:
  StrCpy $SignatureStatus 1
cleanup:
  System::Free $2
  System::Free $1
  System::Free $0
FunctionEnd

Function ValidateExistingUninstaller
  StrCpy $ValidationStatus 1
  StrCpy $ExistingMarkerSigned 0
  StrCpy $ExistingUninstaller "$ExistingDir\Uninstall.exe"
  IfFileExists "$ExistingUninstaller" 0 done
  IfFileExists "$ExistingDir\.sound-mixer-installed" 0 done
  StrCmp $ExistingUninstallString "$\"$ExistingUninstaller$\"" registry_valid
  StrCmp $ExistingUninstallString "$ExistingUninstaller" registry_valid done
registry_valid:
  System::Call 'kernel32::CreateFileW(w "$ExistingDir", i 0, i 7, p 0, i 3, i 0x02000000, p 0) p.r0'
  StrCmp $0 -1 done
  System::StrAlloc ${NSIS_MAX_STRLEN}
  Pop $R0
  System::Call 'kernel32::GetFinalPathNameByHandleW(p r0, p R0, i ${NSIS_MAX_STRLEN}, i 0) i.r1'
  StrCmp $1 0 close_directory
  System::Call '*$R0(&t${NSIS_MAX_STRLEN} .r1)'
  StrCpy $CanonicalExistingDir $1
  System::Call 'kernel32::CreateFileW(w "$ExistingUninstaller", i 0, i 7, p 0, i 3, i 0, p 0) p.r2'
  StrCmp $2 -1 close_directory
  System::Call 'kernel32::GetFinalPathNameByHandleW(p r2, p R0, i ${NSIS_MAX_STRLEN}, i 0) i.r3'
  StrCmp $3 0 close_file
  System::Call '*$R0(&t${NSIS_MAX_STRLEN} .r3)'
  System::Call 'kernel32::lstrcmpiW(w r3, w "$CanonicalExistingDir\Uninstall.exe") i.r4'
  StrCmp $4 0 paths_valid close_file
paths_valid:
  ClearErrors
  FileOpen $4 "$ExistingDir\.sound-mixer-installed" r
  IfErrors close_file
marker_loop:
  ClearErrors
  FileRead $4 $5
  IfErrors marker_done
  StrCmp $5 "signed=1$\r$\n" marker_signed marker_loop
marker_signed:
  StrCpy $ExistingMarkerSigned 1
marker_done:
  FileClose $4
  Call VerifyExistingUninstallerSignature
  StrCmp $SignatureStatus 2 close_file
  StrCmp $ExistingMarkerSigned 1 0 unsigned_allowed
  StrCmp $SignatureStatus 0 signature_allowed close_file
unsigned_allowed:
  !ifdef MACHINE_INSTALL
    StrCmp $ValidationRequireMachinePath 1 0 signature_allowed
    StrCmp $SignatureStatus 1 0 signature_allowed
    System::Call 'kernel32::CreateFileW(w "$PROGRAMFILES64", i 0, i 7, p 0, i 3, i 0x02000000, p 0) p.r4'
    StrCmp $4 -1 close_file
    System::Call 'kernel32::GetFinalPathNameByHandleW(p r4, p R0, i ${NSIS_MAX_STRLEN}, i 0) i.r5'
    StrCmp $5 0 close_program_files
    System::Call '*$R0(&t${NSIS_MAX_STRLEN} .r5)'
    StrCpy $5 "$5\"
    StrLen $6 $5
    StrCpy $7 "$CanonicalExistingDir\" $6
    System::Call 'kernel32::lstrcmpiW(w r7, w r5) i.r6'
    StrCmp $6 0 program_files_valid close_program_files
program_files_valid:
    StrCpy $ValidationStatus 0
close_program_files:
    System::Call 'kernel32::CloseHandle(p r4)'
    Goto close_file
  !endif
signature_allowed:
  StrCpy $ValidationStatus 0
close_file:
  System::Call 'kernel32::CloseHandle(p r2)'
close_directory:
  System::Free $R0
  System::Call 'kernel32::CloseHandle(p r0)'
done:
FunctionEnd
