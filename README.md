- main.py — punto d’ingresso applicazione
- requirements.txt — dipendenze Python progetto
- .gitignore — file esclusioni Git

ai/
- __init__.py — package inizializzazione
- live_voice.py — gestione voce in tempo
- llm.py — integrazione modello linguistico
- prompts.py — prompt per AI
- usage.py — statistiche uso AI

audio/
- __init__.py — package audio
- tts.py — text-to-speech

config/
- habits.json — dati abitudini
- notes.json — appunti utente
- schedules.json — pianificazioni
- settings.yaml — chiavi e configurazioni
- usage.json — uso applicazione

core/
- __init__.py — package core
- engine.py — logica principale
- message_bus.py — gestione messaggi
- scheduler.py — pianificazione eventi

gui/
- __init__.py — package GUI
- app.py — avvio interfaccia
- hologram.py — visualizzazione olografica
- services.py — servizi GUI
- theme.py — tema interfaccia
- widgets.py — componenti UI

tools/
- __init__.py — package strumenti
- habits.py — gestione abitudini
- manager.py — utilità gestione
- sync_tools.py — sincronizzazione dati
- system_tools.py — strumenti sistema
