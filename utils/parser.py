import pandas as pd
import io
import pdfplumber
from typing import List

def extract_items_from_file(file_like) -> List[str]:
    """
    Extrai linhas/itens do arquivo enviado.
    Suporta: csv, xlsx, pdf.
    Retorna lista de strings (cada string = potencial item).
    """
    filename = getattr(file_like, "name", "uploaded_file")
    name = filename.lower()
    items = []

    if name.endswith(".csv"):
        df = pd.read_csv(file_like, dtype=str, keep_default_na=False)
        items = _extract_from_dataframe(df)
    elif name.endswith((".xls", ".xlsx")):
        df = pd.read_excel(file_like, dtype=str, keep_default_na=False)
        items = _extract_from_dataframe(df)
    elif name.endswith(".pdf"):
        text = _extract_text_from_pdf(file_like)
        items = _extract_from_text(text)
    else:
        # try as csv
        try:
            file_like.seek(0)
            df = pd.read_csv(file_like, dtype=str, keep_default_na=False)
            items = _extract_from_dataframe(df)
        except Exception:
            raise ValueError("Formato de arquivo não suportado. Use .csv, .xlsx ou .pdf")

    # limpeza básica
    cleaned = []
    for it in items:
        if not it:
            continue
        if isinstance(it, str) and it.strip():
            cleaned.append(it.strip())
    return cleaned

def _extract_from_dataframe(df: pd.DataFrame):
    # heurística: se existir coluna 'item' ou 'descricao' use ela, senao use todas as células concatenadas por linha
    col_candidates = [c for c in df.columns if c.lower() in ("item", "descricao", "descrição", "produto", "nome")]
    if col_candidates:
        col = col_candidates[0]
        return df[col].astype(str).tolist()
    else:
        # concatena cada linha em uma string
        return df.fillna("").astype(str).agg(" ".join, axis=1).tolist()

def _extract_text_from_pdf(file_like):
    file_like.seek(0)
    text_pages = []
    with pdfplumber.open(file_like) as pdf:
        for page in pdf.pages:
            text_pages.append(page.extract_text() or "")
    return "\n".join(text_pages)

def _extract_from_text(text: str):
    # heurística simples: linhas que parecem itens (com números ou bullets) ou linhas compridas
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # filtrar linhas muito curtas
    lines = [ln for ln in lines if len(ln) > 3]
    # limitar
    return lines