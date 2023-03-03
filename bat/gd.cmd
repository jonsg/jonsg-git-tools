@echo off
if NOT ".%1" == "." goto :xplearg

cd /d %HOMEDRIVE%%HOMEPATH%\git
goto:eof

:xplearg
echo This command takes no arguments
goto :badexit


:badexit
exit /b 1