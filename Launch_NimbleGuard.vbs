Option Explicit

' مشغّل بالنقر المزدوج: يفتح البرنامج من دون نافذة أوامر.
Dim shell, fileSystem, scriptFolder, applicationFile, runner, exitCode
Set shell = CreateObject("WScript.Shell")
Set fileSystem = CreateObject("Scripting.FileSystemObject")

scriptFolder = fileSystem.GetParentFolderName(WScript.ScriptFullName)
applicationFile = scriptFolder & "\NimbleGuard.pyw"

If Not fileSystem.FileExists(applicationFile) Then
    MsgBox "ملف NimbleGuard.pyw غير موجود بجانب المشغّل.", vbCritical + vbOKOnly, "NimbleGuard"
    WScript.Quit 1
End If

' نبحث عن نسخة Python الرسومية فقط؛ لا تظهر نافذة أوامر للمستخدم.
runner = ""
exitCode = shell.Run("cmd /c where pyw.exe >nul 2>nul", 0, True)
If exitCode = 0 Then
    runner = "pyw.exe"
Else
    exitCode = shell.Run("cmd /c where pythonw.exe >nul 2>nul", 0, True)
    If exitCode = 0 Then runner = "pythonw.exe"
End If

If runner = "" Then
    MsgBox "لا توجد Python على الجهاز لتشغيل التطبيق." & vbCrLf & vbCrLf & _
           "ثبّت Python 3.10 أو أحدث مرة واحدة، ثم انقر مرتين على هذا الملف مجدداً.", _
           vbExclamation + vbOKOnly, "NimbleGuard"
    WScript.Quit 1
End If

shell.Run runner & " " & Chr(34) & applicationFile & Chr(34), 0, False
