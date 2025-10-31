import streamlit as st
import pandas as pd
import os
from utils.parser import extract_items_from_file
from utils.ai_integration import normalize_items_with_ai
from utils.scraper import search_all_sources_for_item
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
import time

load_dotenv()

st.set_page_config(page_title="CotaAI - Protótipo", layout="wide")

st.title("CotaAI — Protótipo de Busca de Fornecedores (Streamlit)")
st.markdown(
    """
Envie um arquivo (.xlsx, .csv, .pdf) com a lista de itens.
O sistema usará a API de IA para extrair/normalizar os itens e fará buscas em múltiplas fontes.
"""
)

uploaded_file = st.file_uploader("Carregue o arquivo de cotação", type=["xlsx", "xls", "csv", "pdf"])

col1, col2 = st.columns([1, 3])
with col1:
    max_results_per_site = st.number_input("Resultados por fonte (máx)", min_value=1, max_value=10, value=3)
    concurrency = st.number_input("Threads concorrentes", min_value=1, max_value=12, value=int(os.getenv("MAX_WORKERS", 6)))
    use_ai = st.checkbox("Usar IA para extrair/normalizar itens (OpenAI)", value=True)

with col2:
    st.write("Configurações")
    st.write(f"User agent: `{os.getenv('USER_AGENT', 'default')}`")
    st.write("Fontes: Mercado Livre, OLX, Amazon BR, Shopee, Magazine Luiza, Casas Bahia, AliExpress")

if uploaded_file is None:
    st.info("Faça upload de um arquivo para começar.")
    st.stop()

with st.spinner("Extraindo itens do arquivo..."):
    try:
        raw_items = extract_items_from_file(uploaded_file)
    except Exception as e:
        st.error(f"Erro ao extrair itens: {e}")
        st.stop()

st.write("### Itens extraídos (bruto)")
st.dataframe(pd.DataFrame({"raw": raw_items}))

if use_ai:
    with st.spinner("Normalizando itens com IA..."):
        try:
            items = normalize_items_with_ai(raw_items)
        except Exception as e:
            st.error(f"Erro na integração com IA: {e}")
            st.stop()
else:
    # Básico: strip e dedupe
    items = list({it.strip() for it in raw_items if it and it.strip()})

st.write("### Itens finais para busca")
st.dataframe(pd.DataFrame({"item": items}))

if st.button("Iniciar buscas"):
    results = []
    progress_bar = st.progress(0)
    total_tasks = len(items)
    completed = 0
    start_time = time.time()

    # ThreadPool para paralelizar itens (cada item executa buscas em várias fontes internamente)
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_item = {
            executor.submit(search_all_sources_for_item, item, max_results_per_site): item for item in items
        }

        for future in as_completed(future_to_item):
            item = future_to_item[future]
            try:
                item_results = future.result()
            except Exception as e:
                st.error(f"Erro ao buscar '{item}': {e}")
                item_results = [{"item": item, "origin": None, "title": None, "price": None, "link": None, "status": f"error: {e}"}]
            results.extend(item_results)
            completed += 1
            progress_bar.progress(int(completed / total_tasks * 100))

    df = pd.DataFrame(results)
    st.write(f"### Resultados ({len(df)} registros) — tempo: {time.time() - start_time:.1f}s")
    st.dataframe(df)

    # Allow CSV download
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Baixar resultados (CSV)", csv, "cotaai_results.csv", "text/csv")
