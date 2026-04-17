# 🧭 Bússola — Ferramenta de Jornalismo de Dados

Ferramenta local para apuração baseada em dados e documentos, desenvolvida para jornalistas.

## Instalação

```bash
# 1. Clone ou descompacte o projeto
cd bussola

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute
streamlit run app.py
```

O sistema abrirá automaticamente em `http://localhost:8501`.

## Seções disponíveis

| Seção | Função |
|---|---|
| 📂 Carregar Dados | Upload e raio-x do arquivo |
| 🧹 Limpar e Preparar | Tratamento e padronização |
| 🔎 Explorar Dados | Filtros, rankings e estatísticas |
| 📈 Visualizar | Gráficos interativos (Plotly) |
| 🗺️ Mapas | Visualização territorial por estado ou coordenadas |
| 📄 Extrair de Texto | Entidades, padrões e frequência de termos |
| 📅 Linha do Tempo | Cronologia de eventos |
| 🔄 Comparador | Diff entre arquivos/versões |
| ⚠️ Inconsistências | Alertas automáticos nos dados |
| 💡 Insights de Pauta | Achados e ganchos jornalísticos |
| 📋 Metodologia | Registro de transformações |
| 📓 Bloco de Notas | Anotações e hipóteses |

## Formatos suportados

- **Tabular:** CSV, Excel (.xlsx/.xls), JSON
- **Textual:** TXT, HTML, PDF (via pdfplumber)

## Identidade visual

- Ouro: `#bd8e27`
- Marrom: `#353330`

## Restrições

- Funciona **100% offline** — sem banco externo, sem login, sem API obrigatória
- Dados ficam apenas na memória da sessão
- Projetado para uso individual em redação

---
*Bússola v0.1 — protótipo*
