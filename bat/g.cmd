@echo off
if ".%1" == "." goto :noarg
if NOT ".%2" == "." goto :xplearg

set osbsfilepath=%HOMEDRIVE%%HOMEPATH%\git\%1\os-bs

:chgdir
if not exist "%osbsfilepath%\.gitignore" goto :notexist

cd /d "%osbsfilepath%"
exit /b 0

:noarg
set osbsfilepath=fnord
for /f "delims=" %%i in ('git rev-parse --show-toplevel') do set osbsfilepath=%%i
if not %osbsfilepath%==fnord goto :chgdir
echo.
echo You don't appear to be in a git directory
goto :badexit

:xplearg
echo Only one argument can be provided.
goto :badexit

:notexist
echo %osbsfilepath% doesn't seem to be a valid Telecell repo
goto :badexit


:badexit
exit /b 1