"""Voix off Gemini 3.8 Flash TTS via kie.ai (style libre par phrase, balises d'émotion <laugh>, <whispers>…),
puis timing mot à mot calculé en local avec Whisper (faster-whisper)."""
import re
import subprocess
from pathlib import Path

import kie

_modele = None


def _whisper():
    global _modele
    if _modele is None:
        from faster_whisper import WhisperModel
        _modele = WhisperModel("small", device="cpu", compute_type="int8")
    return _modele


def aligner(audio, texte):
    """Instants de chaque mot prononcé [{t, d, mot}]."""
    propre = re.sub(r"<[^>]+>", "", texte)
    import numpy as np
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", str(audio), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    son = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    segs, _ = _whisper().transcribe(son, language="fr", word_timestamps=True, initial_prompt=propre,
                                    vad_filter=False, beam_size=5)
    mots = []
    for s in segs:
        for w in s.words or []:
            m = w.word.strip()
            if not m:
                continue
            if mots and (m[0] in "'’" or mots[-1]["mot"][-1] in "'’"):   # élisions : « l' » + « airfryer »
                mots[-1]["mot"] += m
                mots[-1]["d"] = float(w.end) - mots[-1]["t"]
                continue
            mots.append({"t": float(w.start), "d": float(w.end - w.start), "mot": m})
    return mots


def voix_off(texte, sortie, voix="Laomedeia", style="", temperature=1.0):
    tid = kie.creer("google/gemini-3-8-flash-tts", {
        "temperature": temperature,
        "speakers": [{"speaker_id": "Speaker 1", "voice_name": voix}],
        "dialogue_turns": [{"speaker_id": "Speaker 1", "text": texte, "style": style}]})
    urls, _ = kie.attendre(tid, pas=3, delai_max=600)
    brut = Path(str(sortie) + ".src")
    kie.telecharger(urls[0], brut)
    # conversion en mp3 + suppression des silences en début/fin pour un rythme serré
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(brut), "-af",
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
                    "silenceremove=start_periods=1:start_threshold=-45dB,areverse",
                    "-ar", "44100", "-ac", "1", "-b:a", "160k", str(sortie)], check=True)
    brut.unlink(missing_ok=True)
    return aligner(sortie, texte)
