@echo off
set PY=C:\Users\Daniel\AppData\Local\Python\pythoncore-3.12-64\python.exe
set PYTEST=C:\Users\Daniel\AppData\Local\Python\pythoncore-3.12-64\Scripts\pytest.exe

echo === Regenerating datasets ===
%PY% research/datasets/scripts/ingest_raw.py
%PY% research/datasets/scripts/process.py
%PY% research/datasets/scripts/split.py

echo === Running C1 tests ===
%PYTEST% research/experiments/01_baseline_prompting/tests/ -q

echo === Done ===
