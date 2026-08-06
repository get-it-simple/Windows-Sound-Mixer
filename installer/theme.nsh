!macro DefineThemeFunctions UN
Function ${UN}ApplyDarkToChildren
  Exch $0
  Push $1
  Push $2
  Push $3
  Push $4
  System::Call 'user32::GetWindow(p r0, i 5) p.r1'
loop:
  StrCmp $1 0 done
  StrCpy $2 $1
  System::Call 'user32::GetClassNameW(p r2, w .r3, i 64) i.r4'
  System::Call 'kernel32::lstrcmpiW(w r3, w "Static") i.r4'
  StrCmp $4 0 static_control
  System::Call 'kernel32::lstrcmpiW(w r3, w "SysListView32") i.r4'
  StrCmp $4 0 list_view
  System::Call 'kernel32::lstrcmpiW(w r3, w "Button") i.r4'
  StrCmp $4 0 0 themed_control
  System::Call 'user32::GetWindowLongW(p r2, i -16) i.r4'
  IntOp $4 $4 & 0xF
  IntCmp $4 2 classic_button themed_control classic_button
classic_button:
  System::Call 'uxtheme::SetWindowTheme(p r2, w "", w "")'
  SetCtlColors $2 FFFFFF 202020
  Goto recurse
list_view:
  System::Call 'uxtheme::SetWindowTheme(p r2, w "DarkMode_Explorer", p 0)'
  SendMessage $2 0x1001 0 0x00202020
  SendMessage $2 0x1024 0 0x00FFFFFF
  SendMessage $2 0x1026 0 0x00202020
  Goto recurse
themed_control:
  System::Call 'kernel32::GetModuleHandleW(w "uxtheme.dll") p.r3'
  StrCmp $3 0 no_dark_api
  System::Call 'kernel32::GetProcAddress(p r3, p 133) p.r4'
  StrCmp $4 0 no_dark_api
  System::Call '::$4(p r2, i 1) i.r4'
no_dark_api:
  System::Call 'uxtheme::SetWindowTheme(p r2, w "DarkMode_Explorer", p 0)'
  SetCtlColors $2 FFFFFF 202020
  Goto recurse
static_control:
  System::Call 'uxtheme::SetWindowTheme(p r2, w "", w "")'
  SetCtlColors $2 FFFFFF 202020
recurse:
  Push $2
  Call ${UN}ApplyDarkToChildren
  System::Call 'user32::GetWindow(p r2, i 2) p.r1'
  Goto loop
done:
  Pop $4
  Pop $3
  Pop $2
  Pop $1
  Pop $0
FunctionEnd

Function ${UN}ApplySystemTheme
  System::Call '*(&l4, i 0, p 0) p.r0'
  System::Call 'user32::SystemParametersInfoW(i 0x42, i 0, p r0, i 0) i.r1'
  System::Call '*$0(i, i .r2, p)'
  System::Free $0
  IntOp $2 $2 & 1
  StrCmp $2 1 done

  ReadRegDWORD $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" "AppsUseLightTheme"
  StrCmp $0 0 0 done

  System::Call 'kernel32::LoadLibraryW(w "uxtheme.dll") p.r3'
  StrCmp $3 0 preferred_mode_done
  System::Call 'kernel32::GetProcAddress(p r3, p 135) p.r4'
  StrCmp $4 0 preferred_mode_done
  System::Call '::$4(i 2) i.r5'
preferred_mode_done:

  System::Call '*(&i4 1) p.r0'
  System::Call 'dwmapi::DwmSetWindowAttribute(p $HWNDPARENT, i 20, p r0, i 4)'
  System::Call 'dwmapi::DwmSetWindowAttribute(p $HWNDPARENT, i 19, p r0, i 4)'
  System::Call '*$0(&i4 0x00202020)'
  System::Call 'dwmapi::DwmSetWindowAttribute(p $HWNDPARENT, i 34, p r0, i 4)'
  System::Call 'dwmapi::DwmSetWindowAttribute(p $HWNDPARENT, i 35, p r0, i 4)'
  System::Call '*$0(&i4 0x00FFFFFF)'
  System::Call 'dwmapi::DwmSetWindowAttribute(p $HWNDPARENT, i 36, p r0, i 4)'
  System::Free $0

  System::Call 'uxtheme::SetWindowTheme(p $HWNDPARENT, w "DarkMode_Explorer", p 0)'
  SendMessage $HWNDPARENT 0x031A 0 0
  SetCtlColors $HWNDPARENT FFFFFF 202020
  Push $HWNDPARENT
  Call ${UN}ApplyDarkToChildren

  FindWindow $0 "#32770" "" $HWNDPARENT
  SetCtlColors $0 FFFFFF 202020
  System::Call 'uxtheme::SetWindowTheme(p r0, w "DarkMode_Explorer", p 0)'
  System::Call 'gdi32::CreateSolidBrush(i 0x00202020) p.r1'
  System::Call 'user32::SetClassLongW(p r0, i -10, p r1) p.r2'

  ; MUI renders the branding label as disabled embossed text by default.
  ; MUI overlays the same text twice. Keep only the original control and
  ; enable it so Windows does not render the disabled embossed shadow.
  GetDlgItem $1 $HWNDPARENT 1028
  System::Call 'user32::EnableWindow(p r1, i 1)'
  System::Call 'uxtheme::SetWindowTheme(p r1, w "", w "")'
  SetCtlColors $1 FFFFFF 202020
  GetDlgItem $1 $HWNDPARENT 1256
  SendMessage $1 0x000C 0 "STR:"

  System::Call 'user32::RedrawWindow(p r0, p 0, p 0, i 0x185)'
  System::Call 'user32::RedrawWindow(p $HWNDPARENT, p 0, p 0, i 0x185)'
done:
FunctionEnd

!macroend

!insertmacro DefineThemeFunctions ""
!insertmacro DefineThemeFunctions "un."
