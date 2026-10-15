; Universal Adept Launcher — retarget shortcuts at the launcher, not Electron.
; The launcher (Adept Launcher.exe) runs first, performs the signed-catalog
; update check from outside the payload, then boots the real Electron app.
; Electron itself performs no update handoff.

!macro ADEPT_RETARGET_SHORTCUTS
  ; Desktop shortcut -> launcher
  ${If} ${FileExists} "$DESKTOP\Adept UI.lnk"
  ${AndIf} ${FileExists} "$INSTDIR\Adept Launcher.exe"
    CreateShortCut "$DESKTOP\Adept UI.lnk" "$INSTDIR\Adept Launcher.exe" "" "$INSTDIR\Adept Launcher.exe" 0
  ${EndIf}

  ; Start Menu shortcut -> launcher
  ${If} ${FileExists} "$SMPROGRAMS\Adept UI\Adept UI.lnk"
  ${AndIf} ${FileExists} "$INSTDIR\Adept Launcher.exe"
    CreateShortCut "$SMPROGRAMS\Adept UI\Adept UI.lnk" "$INSTDIR\Adept Launcher.exe" "" "$INSTDIR\Adept Launcher.exe" 0
  ${EndIf}
!macroend

!macro customInstall
  !insertmacro ADEPT_RETARGET_SHORTCUTS
!macroend

!macro customInstallMode
  !insertmacro ADEPT_RETARGET_SHORTCUTS
!macroend
