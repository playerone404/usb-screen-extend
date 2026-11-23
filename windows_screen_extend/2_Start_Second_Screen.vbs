Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonwExe = ""

' Check PATH pythonw
On Error Resume Next
Set exec = WshShell.Exec("where pythonw.exe")
If exec.Status = 0 Then
    line = exec.StdOut.ReadLine()
    If fso.FileExists(line) Then pythonwExe = line
End If
On Error GoTo 0

' Fallback standard locations
If pythonwExe = "" Then
    If fso.FileExists("C:\Platform-tool\platform-tools\pythonw.exe") Then
        pythonwExe = "C:\Platform-tool\platform-tools\pythonw.exe"
    ElseIf fso.FileExists(WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe")) Then
        pythonwExe = WshShell.ExpandEnvironmentStrings("%LOCALAPPDATA%\Programs\Python\Python311\pythonw.exe")
    Else
        pythonwExe = "pythonw.exe"
    End If
End If

trayScript = scriptDir & "\core\tray_app.py"
cmd = """" & pythonwExe & """ """ & trayScript & """"
WshShell.Run cmd, 0, False
