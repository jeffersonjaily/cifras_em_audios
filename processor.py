# processor.py
import soundfile as sf
from basic_pitch.inference import predict
from music21 import converter, chord

def process_audio_with_lyrics(audio_path, letra_texto):
    audio, sr = sf.read(audio_path)
    _, _, note_events = predict(audio, sr)
    
    versos = letra_texto.splitlines()
    resultado = []

    notas = [event["note"] for event in note_events if event["confidence"] > 0.9]
    notas = notas[:len(versos)] if len(notas) >= len(versos) else notas + [60] * (len(versos) - len(notas))

    for i, verso in enumerate(versos):
        if verso.strip():
            acorde = nota_para_acorde(notas[i])
            resultado.append(f"{verso.strip()} -> {acorde}")
    return "\n".join(resultado)

def nota_para_acorde(note_number):
    pitch_classes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    return pitch_classes[note_number % 12]
