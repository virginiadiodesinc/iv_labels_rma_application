@echo off
powershell -NoProfile -Command ^
  "$ws = New-Object -ComObject WScript.Shell; " ^
  "$s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\IV Labels App.lnk'); " ^
  "$s.TargetPath = 'C:\Windows\System32\cmd.exe'; " ^
  "$s.Arguments = '/c \"%~dp0..\launcher.bat\"'; " ^
  "$s.WorkingDirectory = '%~dp0..\'; " ^
  "$s.IconLocation = '%~dp0..\app\static\img\IVL.ico,0'; " ^
  "$s.Save()"
echo Shortcut created on your Desktop.
pause