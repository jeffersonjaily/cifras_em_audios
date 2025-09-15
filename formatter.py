# formatter.py (Versão Final com Cifras Instrumentais)

def _formatar_linha_de_cifras(lista_acordes):
    """Pega uma lista de nomes de acordes e os formata em uma string."""
    return "   ".join(lista_acordes)

def alinhar_cifras_e_letra(segmentos_letra, acordes_com_tempo):
    """
    Alinha cifras e letras, agora incluindo seções instrumentais (intro, solos, outro).
    """
    if not acordes_com_tempo:
        # Se não há acordes, retorna apenas a letra formatada.
        texto_so_letra = "\n\n".join([" ".join([p['word'].strip() for p in s.get('words', [])]) for s in segmentos_letra])
        return texto_so_letra

    resultado_final = []
    idx_acorde_atual = 0
    ultimo_tempo_processado = 0.0

    # Itera sobre cada segmento de letra (verso, refrão, etc.)
    for i, segmento in enumerate(segmentos_letra):
        palavras = segmento.get('words', [])
        if not palavras: continue

        inicio_segmento = segmento['start']
        
        # --- LÓGICA PARA PARTES INSTRUMENTAIS ANTES DO VERSO ATUAL ---
        # Verifica se há um espaço de tempo entre o último processamento e o verso atual
        if inicio_segmento > ultimo_tempo_processado + 2.0: # Tolerância de 2s
            acordes_no_intervalo = []
            # Coleta todos os acordes nesse intervalo de tempo
            while idx_acorde_atual < len(acordes_com_tempo) and acordes_com_tempo[idx_acorde_atual]['tempo'] < inicio_segmento:
                acorde_info = acordes_com_tempo[idx_acorde_atual]
                # Evita duplicatas
                if not acordes_no_intervalo or acordes_no_intervalo[-1] != acorde_info['acorde']:
                    acordes_no_intervalo.append(acorde_info['acorde'])
                idx_acorde_atual += 1
            
            if acordes_no_intervalo:
                # Se for antes do primeiro verso, é a Intro. Senão, é Instrumental.
                titulo_secao = "[Intro]" if i == 0 else "[Instrumental]"
                resultado_final.append(titulo_secao)
                resultado_final.append(_formatar_linha_de_cifras(acordes_no_intervalo))
                resultado_final.append("")

        # --- LÓGICA PADRÃO PARA ALINHAR CIFRAS E LETRAS (JÁ FUNCIONAVA) ---
        linha_letra = ""
        posicoes_palavras = []
        for p in palavras:
            posicoes_palavras.append({'start': p['start'], 'pos': len(linha_letra)})
            linha_letra += p['word'].strip() + " "
        
        linha_letra = linha_letra.rstrip()
        linha_cifras = list(' ' * len(linha_letra))
        
        acordes_deste_segmento_indices = []
        temp_idx = idx_acorde_atual
        while temp_idx < len(acordes_com_tempo) and acordes_com_tempo[temp_idx]['tempo'] <= segmento['end'] + 0.2:
            acordes_deste_segmento_indices.append(temp_idx)
            temp_idx += 1

        for idx_acorde in acordes_deste_segmento_indices:
            acorde = acordes_com_tempo[idx_acorde]
            tempo_acorde = acorde['tempo']
            
            palavra_alvo = None
            for j, p_info in enumerate(posicoes_palavras):
                inicio_p = p_info['start']
                fim_p = posicoes_palavras[j+1]['start'] if j + 1 < len(posicoes_palavras) else segmento['end']
                if inicio_p <= tempo_acorde < fim_p:
                    palavra_alvo = p_info
                    break
            
            if palavra_alvo:
                nome_acorde = acorde['acorde']
                pos_char = palavra_alvo['pos']
                for k, char in enumerate(nome_acorde):
                    if pos_char + k < len(linha_cifras):
                        linha_cifras[pos_char + k] = ' ' # Limpa espaço para o acorde
                for k, char in enumerate(nome_acorde):
                    if pos_char + k < len(linha_cifras):
                        linha_cifras[pos_char + k] = char

        idx_acorde_atual = temp_idx # Atualiza o cursor principal de acordes
        
        linha_cifras_str = "".join(linha_cifras).rstrip()
        if linha_cifras_str:
            resultado_final.append(linha_cifras_str)
        resultado_final.append(linha_letra)
        resultado_final.append("")
        
        ultimo_tempo_processado = segmento['end']

    # --- LÓGICA PARA O OUTRO (ACORDES APÓS A ÚLTIMA LETRA) ---
    acordes_restantes = []
    while idx_acorde_atual < len(acordes_com_tempo):
        acorde_info = acordes_com_tempo[idx_acorde_atual]
        if not acordes_restantes or acordes_restantes[-1] != acorde_info['acorde']:
            acordes_restantes.append(acorde_info['acorde'])
        idx_acorde_atual += 1
    
    if acordes_restantes:
        resultado_final.append("[Outro]")
        resultado_final.append(_formatar_linha_de_cifras(acordes_restantes))
        resultado_final.append("")

    return "\n".join(resultado_final)