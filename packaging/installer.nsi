; Optimuslock Windows kurulum paketi (NSIS 3, Linux üzerinde çapraz derlenir)
Unicode true
!include "MUI2.nsh"

!ifndef VERSION
  !define VERSION "1.0.0"
!endif

Name "Optimuslock ${VERSION}"
OutFile "..\dist\Optimuslock-Setup-${VERSION}.exe"
InstallDir "$PROGRAMFILES64\Optimuslock"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
SetCompressorDictSize 64
BrandingText "Optimuslock"

!define MUI_ICON "build\optimuslock.ico"
!define MUI_UNICON "build\optimuslock.ico"
!define MUI_ABORTWARNING
!define MUI_FINISHPAGE_TITLE "Optimuslock kuruldu"
!define MUI_FINISHPAGE_TEXT "Kurulum tamamlandı.$\r$\n$\r$\nBaşlatmak için masaüstündeki Optimuslock simgesine çift tıklayın; ilk açılışta Öğrenci / Öğretmen ve bağlantı yöntemi (Tailscale / IP) seçilir."

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Turkish"

Section "Optimuslock" SecMain
  SetShellVarContext all
  SetOutPath "$INSTDIR"
  File "build\optimuslock.ico"
  SetOutPath "$INSTDIR\python"
  File /r "build\stage\python\*.*"
  SetOutPath "$INSTDIR\app"
  File "build\stage\app\*.py"
  SetOutPath "$INSTDIR\docker"
  File "build\stage\docker\*.*"

  ; Gelen bağlantı için güvenlik duvarı kuralı (varsayılan port 5710)
  nsExec::Exec 'netsh advfirewall firewall delete rule name="Optimuslock"'
  nsExec::Exec 'netsh advfirewall firewall add rule name="Optimuslock" dir=in action=allow protocol=TCP localport=5710 profile=any'

  CreateDirectory "$SMPROGRAMS\Optimuslock"
  CreateShortcut "$SMPROGRAMS\Optimuslock\Optimuslock.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\app\optimuslock.py"' "$INSTDIR\optimuslock.ico" 0
  CreateShortcut "$SMPROGRAMS\Optimuslock\Optimuslock Kurulum Ekranı.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\app\optimuslock.py" --setup' "$INSTDIR\optimuslock.ico" 0
  CreateShortcut "$SMPROGRAMS\Optimuslock\Tailscale Docker (Windows).lnk" "$INSTDIR\docker\tailscale_docker_windows.bat" "" "$INSTDIR\optimuslock.ico" 0
  CreateShortcut "$DESKTOP\Optimuslock.lnk" "$INSTDIR\python\pythonw.exe" '"$INSTDIR\app\optimuslock.py"' "$INSTDIR\optimuslock.ico" 0

  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Optimuslock" "DisplayName" "Optimuslock"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Optimuslock" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Optimuslock" "DisplayIcon" "$INSTDIR\optimuslock.ico"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Optimuslock" "Publisher" "Optimuslock"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Optimuslock" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Optimuslock" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Optimuslock" "NoModify" 1
SectionEnd

Section "Uninstall"
  SetShellVarContext all
  nsExec::Exec 'netsh advfirewall firewall delete rule name="Optimuslock"'
  DeleteRegValue HKCU "Software\Microsoft\Windows\CurrentVersion\Run" "Optimuslock"
  Delete "$DESKTOP\Optimuslock.lnk"
  RMDir /r "$SMPROGRAMS\Optimuslock"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Optimuslock"
  RMDir /r /REBOOTOK "$INSTDIR"
SectionEnd
