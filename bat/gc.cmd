@echo off
if ".%1" == "." goto :noarg
if NOT ".%2" == "." goto :xplearg

set gitpath=%HOMEDRIVE%%HOMEPATH%\git
set repopath=%gitpath%\%1

cd /d %gitpath%
if errorlevel 1 goto :nopath

if exist %1 goto :alreadyexist

mkdir %1
if errorlevel 1 goto :cantmake
if not exist %1 goto :whereisit

cd %1
if errorlevel 1 goto :cantcd

git clone ssh://git@code.gb-cmg001.lan.intra.lighting.com:7999/lug/os-bs.git
if errorlevel 1 goto :clonebroke

set tgtdir=os-bs
if not exist %tgtdir% goto :notgtdir
cd %tgtdir%
if errorlevel 1 goto :notgtdircd

exit /b 0

:notgtdircd
echo %repopath%\%tgtdir% appears to exist but can't cd to it.
goto :badexit

:notgtdir
echo "Cloned, but can't find %tgtdir% in %repopath%
goto :badexit

:clonebroke
echo "Failed to clone in %repopath%.
goto :badexit

:cantcd
echo Created %repopath%, but can't cd to it.
goto :badexit

:whereisit
echo Tried to make %repopath% and that succeeded, but
echo I can't find it now.
goto :badexit

:cantmake
echo It wasn't possible to make %repopath%.
goto :badexit

:alreadyexist
echo The file or directory %1 already exists.
goto :badexit

:nopath
echo Apparently, %gitpath% doesn't exist.
goto :badexit


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


:badexit
exit /b 1