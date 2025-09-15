# main.py

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import threading
import queue
import os
# NOVO: Imports para a funcionalidade de playback
import sounddevice as sd
import soundfile as sf

import audio_processor
import formatter
import exporter

class AppCifrador(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Analisador Musical Pro v9.0 (com Playback)")
        self.geometry("900x700")

        self.audio_path = None
        self.resultado_final = ""
        self.analysis_queue = queue.Queue()
        self.cancel_event = threading.Event()
        
        # NOVO: Controle de estado do playback
        self.is_playing = False

        self._criar_widgets()

    def _criar_widgets(self):
        """Cria todos os elementos da interface gráfica."""
        main_frame = tk.Frame(self, padx=10, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        controls_frame = tk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=5)

        self.load_button = tk.Button(controls_frame, text="1. Carregar Áudio", command=self.carregar_audio)
        self.load_button.pack(side=tk.LEFT, padx=5)

        # NOVO: Botão de Play/Parar
        self.play_button = tk.Button(controls_frame, text="▶️ Ouvir", command=self.toggle_playback, state=tk.DISABLED)
        self.play_button.pack(side=tk.LEFT, padx=5)

        self.analyze_button = tk.Button(controls_frame, text="2. Analisar Música", command=self.iniciar_analise, state=tk.DISABLED)
        self.analyze_button.pack(side=tk.LEFT, padx=15)
        
        self.cancel_button = tk.Button(controls_frame, text="Cancelar Análise", command=self.cancelar_analise, state=tk.DISABLED, bg="#ff8a80")
        self.cancel_button.pack(side=tk.LEFT, padx=5)

        options_frame = tk.Frame(main_frame)
        options_frame.pack(fill=tk.X, pady=5, anchor='w')

        tk.Label(options_frame, text="Qualidade da Transcrição:").pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value="medium")
        model_options = ["base", "small", "medium"]
        self.model_menu = ttk.OptionMenu(options_frame, self.model_var, model_options[2], *model_options)
        self.model_menu.pack(side=tk.LEFT, padx=5)
        
        self.clear_cache_button = tk.Button(options_frame, text="Limpar Cache", command=self.limpar_cache_gui)
        self.clear_cache_button.pack(side=tk.LEFT, padx=20)

        results_frame = tk.Frame(main_frame)
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        save_frame = tk.Frame(results_frame)
        save_frame.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(save_frame, text="3. Salvar como:").pack(side=tk.LEFT)
        self.save_txt_button = tk.Button(save_frame, text="TXT", command=lambda: self.salvar_resultado('txt'), state=tk.DISABLED)
        self.save_txt_button.pack(side=tk.LEFT, padx=2)
        self.save_pdf_button = tk.Button(save_frame, text="PDF", command=lambda: self.salvar_resultado('pdf'), state=tk.DISABLED)
        self.save_pdf_button.pack(side=tk.LEFT, padx=2)
        self.save_docx_button = tk.Button(save_frame, text="DOCX", command=lambda: self.salvar_resultado('docx'), state=tk.DISABLED)
        self.save_docx_button.pack(side=tk.LEFT, padx=2)

        self.result_area = scrolledtext.ScrolledText(results_frame, width=80, height=25, font=("Courier New", 10))
        self.result_area.pack(fill=tk.BOTH, expand=True)

        status_frame = tk.Frame(main_frame, padx=10, pady=5)
        status_frame.pack(fill=tk.X)
        self.status_label = tk.Label(status_frame, text="Pronto. Carregue um arquivo de áudio para começar.")
        self.status_label.pack(side=tk.LEFT)

    def carregar_audio(self):
        if self.is_playing:
            self.stop_playback()
            
        self.audio_path = filedialog.askopenfilename(filetypes=[("Arquivos de Áudio", "*.wav *.mp3 *.m4a")])
        if self.audio_path:
            filename = os.path.basename(self.audio_path)
            self.status_label.config(text=f"Áudio carregado: {filename}")
            self.analyze_button.config(state=tk.NORMAL)
            self.play_button.config(state=tk.NORMAL)
            self.result_area.delete("1.0", tk.END)
            self.resultado_final = ""
            self.set_save_buttons_state(tk.DISABLED)

    def iniciar_analise(self):
        self.cancel_event.clear()
        self.set_ui_state_ocupado(True)
        self.result_area.delete("1.0", tk.END)
        
        selected_model = self.model_var.get()
        thread = threading.Thread(target=self.thread_de_analise, args=(self.audio_path, selected_model, self.cancel_event))
        thread.daemon = True
        thread.start()

        self.after(100, self.verificar_fila)

    # --- FUNÇÕES DE PLAYBACK ---
    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self):
        if not self.audio_path: return
        self.is_playing = True
        self.play_button.config(text="⏹️ Parar")
        self._set_main_buttons_state(tk.DISABLED)

        playback_thread = threading.Thread(target=self._play_audio_worker, daemon=True)
        playback_thread.start()

    def stop_playback(self):
        sd.stop()
        self.is_playing = False
        self.play_button.config(text="▶️ Ouvir")
        self._set_main_buttons_state(tk.NORMAL)

    def _play_audio_worker(self):
        try:
            data, samplerate = sf.read(self.audio_path, dtype='float32')
            sd.play(data, samplerate)
            sd.wait()
        except Exception as e:
            self.analysis_queue.put(("erro", f"Não foi possível tocar o áudio:\n{e}"))
        finally:
            self.analysis_queue.put(("playback_finished", None))
    # --- FIM DAS FUNÇÕES DE PLAYBACK ---

    def cancelar_analise(self):
        self.status_label.config(text="Cancelando... Aguarde a finalização do passo atual.")
        self.cancel_event.set()
        self.cancel_button.config(state=tk.DISABLED)

    def limpar_cache_gui(self):
        if self.is_playing: self.stop_playback()
        if messagebox.askyesno("Limpar Cache", "Isso apagará todos os resultados salvos. Deseja continuar?"):
            audio_processor.limpar_cache()
            messagebox.showinfo("Sucesso", "O cache foi limpo com sucesso.")
            self.status_label.config(text="Cache limpo. Pronto.")

    def thread_de_analise(self, audio_path, model_size, cancel_event):
        def atualizar_status_da_thread(mensagem):
            self.analysis_queue.put(("status", mensagem))

        try:
            segmentos_letra = audio_processor.transcrever_audio_com_timestamps(audio_path, model_size, atualizar_status_da_thread, cancel_event)
            if cancel_event.is_set():
                self.analysis_queue.put(("cancelado", None)); return

            acordes_com_tempo = audio_processor.extrair_acordes_com_timestamps(audio_path, atualizar_status_da_thread, cancel_event)
            if cancel_event.is_set():
                self.analysis_queue.put(("cancelado", None)); return
            
            atualizar_status_da_thread("Análise concluída. Formatando o resultado...")
            resultado_formatado = formatter.alinhar_cifras_e_letra(segmentos_letra, acordes_com_tempo)
            
            self.analysis_queue.put(("resultado", resultado_formatado))
        except Exception as e:
            if not cancel_event.is_set():
                self.analysis_queue.put(("erro", f"Ocorreu um erro:\n\n{e}"))

    def verificar_fila(self):
        try:
            tipo_msg, dados = self.analysis_queue.get_nowait()
            
            if tipo_msg == "playback_finished":
                if self.is_playing: self.stop_playback()
            elif tipo_msg == "status":
                self.status_label.config(text=dados)
            elif tipo_msg == "resultado":
                self.resultado_final = dados
                self.result_area.insert(tk.END, dados)
                self.status_label.config(text="Análise concluída com sucesso!")
                self.set_ui_state_ocupado(False)
                if self.resultado_final and self.resultado_final.strip():
                    self.set_save_buttons_state(tk.NORMAL)
                return 
            elif tipo_msg == "cancelado":
                self.status_label.config(text="Análise cancelada pelo usuário.")
                self.set_ui_state_ocupado(False)
                return
            elif tipo_msg == "erro":
                messagebox.showerror("Erro na Análise", dados)
                self.status_label.config(text="Ocorreu um erro.")
                self.set_ui_state_ocupado(False)
                return
        
        except queue.Empty: pass 
        self.after(100, self.verificar_fila)

    def salvar_resultado(self, formato):
        if not self.resultado_final or not self.resultado_final.strip():
            messagebox.showwarning("Nada para Salvar", "Nenhum resultado para salvar.")
            return

        filetypes = { 'txt': [("Arquivo de Texto", "*.txt")], 'pdf': [("Documento PDF", "*.pdf")], 'docx': [("Documento Word", "*.docx")] }
        caminho = filedialog.asksaveasfilename(defaultextension=f".{formato}", filetypes=filetypes[formato])

        if not caminho: return

        try:
            exporter_map = {'txt': exporter.exportar_para_txt, 'pdf': exporter.exportar_para_pdf, 'docx': exporter.exportar_para_docx}
            exporter_map[formato](self.resultado_final, caminho)
            messagebox.showinfo("Sucesso", f"Arquivo salvo com sucesso em:\n{caminho}")
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo:\n{e}")

    def _set_main_buttons_state(self, state):
        self.load_button.config(state=state)
        self.analyze_button.config(state=state if self.audio_path and state==tk.NORMAL else tk.DISABLED)

    def set_ui_state_ocupado(self, ocupado: bool):
        if ocupado:
            self._set_main_buttons_state(tk.DISABLED)
            self.play_button.config(state=tk.DISABLED)
            self.model_menu.config(state=tk.DISABLED)
            self.clear_cache_button.config(state=tk.DISABLED)
            self.cancel_button.config(state=tk.NORMAL)
            self.set_save_buttons_state(tk.DISABLED)
        else: # Não ocupado
            self._set_main_buttons_state(tk.NORMAL)
            self.play_button.config(state=tk.NORMAL if self.audio_path else tk.DISABLED)
            self.model_menu.config(state=tk.NORMAL)
            self.clear_cache_button.config(state=tk.NORMAL)
            self.cancel_button.config(state=tk.DISABLED)

    def set_save_buttons_state(self, estado):
        self.save_txt_button.config(state=estado)
        self.save_pdf_button.config(state=estado)
        self.save_docx_button.config(state=estado)

if __name__ == "__main__":
    app = AppCifrador()
    app.mainloop()