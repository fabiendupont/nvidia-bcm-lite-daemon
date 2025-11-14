@echo off
rem
rem Install modules needed to run cm-lite-daemon
rem
rem Assumes pip is installed and added to the %PATH%
rem

pip install --upgrade pip
pip install -rrequirements.txt
