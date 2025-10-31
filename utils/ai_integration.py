import os
import openai
from typing import List

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_KEY:
    openai.api_key = OPENAI_KEY

def normalize_items_with_ai(raw_items: List[str]) -> List[str]:
    """
    Envia os itens brutos para a OpenAI (ou outro LLM) e pede para limpar, normalizar e deduplicar.
    Retorna lista de strings prontas para busca.
    """
    if not OPENAI_KEY:
        # fallback: strip + dedupe
        return list({it.strip() for it in raw_items if it and it.strip()})

    prompt = _build_prompt(raw_items)
    resp = openai.ChatCompletion.create(
        model="gpt-4o-mini",  # ajuste conforme sua conta / disponibilidade
        messages=[
            {"role": "system", "content": "Você é um assistente que transforma listas de itens de compra em nomes curtos e normalizados."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0,
        max_tokens=800
    )
    text = resp["choices"][0]["message"]["content"].strip()
    # assumir que a resposta é uma lista com linhas
    normalized = [line.strip("-• \t\n\r") for line in text.splitlines() if line.strip()]
    # última segurança: dedupe preservando ordem
    seen = set()
    out = []
    for it in normalized:
        if it.lower() in seen: 
            continue
        seen.add(it.lower())
        out.append(it)
    return out

def _build_prompt(raw_items):
    sample = "\n".join(f"- {it}" for it in raw_items[:80])  # limitar
    return (
        "Transforme a lista a seguir em nomes curtos e normalizados de produtos, removendo quantidades, unidades e observações, "
        "retornando apenas uma lista com um produto por linha. Deduplique e corrija nomes óbvios.\n\n"
        f"Lista:\n{sample}\n\nResposta (apenas a lista, uma linha por item):"
    )
