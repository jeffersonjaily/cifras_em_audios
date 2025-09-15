# audio_processor.py

import torch
import whisper
import os
import tempfile
import soundfile as sf
import hashlib
import json
import shutil
from demucs.api import Separator
from demucs.audio import save_audio
from madmom.features.chords import CNNChordFeatureProcessor, CRFChordRecognitionProcessor
from madmom.processors import SequentialProcessor

# --- CONFIGURAÇÕES GLOBAIS ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Dispositivo de processamento para Whisper selecionado: {DEVICE.upper()}")
LOADED_WHISPER_MODELS = {}
CACHE_DIR = ".cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def _get_file_hash(filepath):
    """Cria um hash MD5 para um arquivo para usar como chave de cache."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read(65536) # Lê em blocos para arquivos grandes
        while len(buf) > 0:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()

def limpar_cache():
    """Apaga a pasta de cache e a recria."""
    if os.path.exists(CACHE_DIR):
        try:
            shutil.rmtree(CACHE_DIR)
            os.makedirs(CACHE_DIR, exist_ok=True)
            print("Cache limpo com sucesso.")
            return True
        except Exception as e:
            print(f"Erro ao limpar cache: {e}")
            return False
    return True

def _carregar_modelo_whisper(model_size="medium"):
    """Carrega um modelo do Whisper sob demanda e o armazena em cache na memória."""
    if model_size not in LOADED_WHISPER_MODELS:
        print(f"Carregando modelo Whisper ({model_size})...")
        LOADED_WHISPER_MODELS[model_size] = whisper.load_model(model_size, device=DEVICE)
        print(f"Modelo Whisper ({model_size}) carregado.")
    return LOADED_WHISPER_MODELS[model_size]

def transcrever_audio_com_timestamps(audio_path: str, model_size: str, status_callback, cancel_event):
    """Transcreve o áudio, usando cache e permitindo cancelamento."""
    file_hash = _get_file_hash(audio_path)
    cache_key = f"{file_hash}_{model_size}_transcription.json"
    cache_path = os.path.join(CACHE_DIR, cache_key)

    if os.path.exists(cache_path):
        status_callback("Resultado da transcrição encontrado no cache. Carregando...")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    caminho_vocal_temporario = None
    try:
        status_callback("Separando vocais com Demucs... (pode ser lento na 1ª vez)")
        separator = Separator()
        origin, separated = separator.separate_audio_file(audio_path)
        
        if cancel_event.is_set(): return None

        vocais = separated.get('vocals')
        if vocais is None: raise RuntimeError("Não foi possível extrair os vocais.")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmpfile:
            caminho_vocal_temporario = tmpfile.name
            save_audio(vocais, caminho_vocal_temporario, samplerate=separator.samplerate)
        
        if cancel_event.is_set(): return None

        status_callback(f"Transcrevendo com Whisper (modelo {model_size})...")
        modelo_whisper = _carregar_modelo_whisper(model_size)
        resultado = modelo_whisper.transcribe(caminho_vocal_temporario, language="pt", word_timestamps=True)
        
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(resultado['segments'], f, ensure_ascii=False, indent=4)
            
        return resultado['segments']
    finally:
        if caminho_vocal_temporario and os.path.exists(caminho_vocal_temporario):
            os.remove(caminho_vocal_temporario)

def extrair_acordes_com_timestamps(audio_path: str, status_callback, cancel_event):
    """Extrai acordes, usando cache e permitindo cancelamento."""
    file_hash = _get_file_hash(audio_path)
    cache_key = f"{file_hash}_chords.json"
    cache_path = os.path.join(CACHE_DIR, cache_key)
    
    if os.path.exists(cache_path):
        status_callback("Resultado das cifras encontrado no cache. Carregando...")
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    status_callback("Analisando acordes com Madmom...")
    feature_processor = CNNChordFeatureProcessor()
    chord_decoder = CRFChordRecognitionProcessor()
    pipeline = SequentialProcessor([feature_processor, chord_decoder])
    dados_acordes = pipeline(audio_path)

    if cancel_event.is_set(): return None

    acordes_com_tempo = []
    acorde_anterior = None
    for inicio, _, nome_acorde in dados_acordes:
        if nome_acorde == 'N': continue
        if ':' in nome_acorde:
            raiz, tipo = nome_acorde.split(':')
            if 'maj' in tipo: nome_formatado = raiz
            elif 'min' in tipo: nome_formatado = f"{raiz}m"
            else: nome_formatado = nome_acorde.replace(':', '')
        else: nome_formatado = nome_acorde
        if nome_formatado != acorde_anterior:
            acordes_com_tempo.append({'acorde': nome_formatado, 'tempo': inicio})
            acorde_anterior = nome_formatado

    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(acordes_com_tempo, f, ensure_ascii=False, indent=4)

    return acordes_com_tempo