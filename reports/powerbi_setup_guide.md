# Guia de Integração — Power BI: Brazilian Rates Intelligence

Este documento explica como conectar o Power BI diretamente aos dados do **Brazilian Rates Intelligence**, espelhando exatamente as **6 abas do Streamlit** no padrão visual executivo do `Brazil_Equity_Research.pbix`.

---

## 1. Arquitetura da Ligação Direta com a Base de Dados

O pipeline em Python (`scripts/export_powerbi_data.py`) extrai, trata e calcula todas as métricas quantitativas (B3/ANBIMA, Banco Central SGS/Focus e Yahoo Finance) e salva as tabelas prontas na pasta:
`c:\Users\Marcos\Desktop\Brazilian Rates Intelligence\data\powerbi\`

### Como funciona a sincronização:
1. Sempre que você quiser atualizar os dados de mercado, execute no terminal:
   ```bash
   python scripts/export_powerbi_data.py
   ```
2. No Power BI Desktop, basta clicar no botão **"Atualizar" (Refresh)** na barra superior: todas as 6 abas carregarão os dados mais recentes instantaneamente.

---

## 2. As 6 Tabelas e Abas Espelhadas do Streamlit

| Aba no Power BI | Tabela Fonte | Conteúdo & Visualizações |
| :--- | :--- | :--- |
| **1. Macro Overview** | `1_Macro_Overview.csv` | **KPI Cards**: Selic, IPCA 12m, USD/BRL, Focus IPCA, Dívida/PIB.<br>**Gráficos**: Selic vs Focus (Linhas), IPCA 12m (Área), USD/BRL e Câmbio/Desemprego (Colunas/Linhas), Matriz de Correlação Macro. |
| **2. Yield Curve** | `2_Yield_Curve_Snapshots.csv`<br>`2_Yield_Curve_TimeSeries.csv` | **KPI Cards**: Nível da Curva, Slope (10Y-2Y), Curvatura, Real Yield.<br>**Gráficos**: Estrutura a Termo Atual vs 1m / 3m / 1a atrás (Linhas por Vértice), Evolução Temporal de Slope/Curvature/Real Yield. |
| **3. Market Regimes** | `3_Market_Regimes.csv`<br>`3_Regime_Performance.csv` | **KPI Cards**: Regime Atual (Risk-on, Risk-off, Inflacionário, Desinflacionário), Confiança do Sinal, Duração.<br>**Gráficos**: Timeline histórica dos regimes (Dispersão/Linhas), Z-Scores dos drivers macro, Matriz de Retorno e Volatilidade por Regime. |
| **4. Event Studies** | `4_Event_Study_CAR.csv`<br>`4_Events_Catalog.csv` | **KPI Cards**: Total de Eventos, CAR t+5, T-Stat, Significância estatística.<br>**Gráficos**: Trajetória Média do Retorno Anormal Acumulado (CAR [-5, +20]) com Bandas de Confiança de 95%, Tabela Multi-Ativos (Ibov, USD, IMAB11). |
| **5. Asset Impact** | `5_Asset_Impact_Responses.csv`<br>`5_Asset_Impact_Heatmap.csv`<br>`5_Asset_Impact_LeadLag.csv` | **KPI Cards**: Cenário de Choque (+100bps, -100bps, etc.), Retorno Mediano 21d de Ibovespa, Dólar e IMAB11.<br>**Gráficos**: Heatmap de sensibilidade cruzada (Matriz com formatação condicional), Gráfico de Barras Lead/Lag (-20 a +20 dias). |
| **6. Rates Signal** | `6_Rates_Signal.csv`<br>`6_Rates_Signal_Backtest.csv` | **KPI Cards**: Rates Pressure Score (-100 a +100), Diagnóstico, Acurácia Direcional, IC de Spearman.<br>**Gráficos**: Gauge/Medidor do Score, Decomposição em Barras dos 4 Pilares (Inflação, Fiscal, FX, Monetário), Histórico do Score vs Curva, Tabela de Backtest. |

---

## 3. O que NÃO é possível nativamente no Power BI e o MOTIVO

Conforme solicitado, analisamos as diferenças técnicas entre o motor do Streamlit/Python e o motor do Power BI (DAX / VertiPaq):

### 1. Geração de arquivo `.pbix` binário 100% fechado por código externo
- **Motivo**: O formato `.pbix` armazena o modelo de dados em um banco de dados interno proprietário (`DataModel`) compilado pelo Analysis Services da Microsoft. Nenhuma ferramenta ou biblioteca oficial fora do próprio Power BI Desktop consegue compilar esse binário do zero sem corromper a assinatura do arquivo.
- **Como é resolvido**: O Power BI consome as tabelas relacionais geradas pelo Python com os tipos de dados já corretos e estruturados.

### 2. Algoritmos de Machine Learning Dinâmicos no DAX (GMM / Gaussian Mixture Models)
- **Motivo**: O DAX é uma linguagem de consulta e agregação analítica tabular. Ele não possui bibliotecas de clustering probabilístico avançado como o `scikit-learn`.
- **Como é resolvido**: O script `export_powerbi_data.py` executa o GMM e a lógica quantitativa no Python e já entrega a coluna de `Regime` e `Confidence` calculada na tabela fato do Power BI.

### 3. Superfície 3D da Curva (Surface 3D Plot do Plotly)
- **Motivo**: O Power BI não possui visual 3D nativo na biblioteca padrão para renderização de curvas tridimensionais em malha contínua.
- **Como é resolvido**: Utiliza-se a **Matriz com Formatação Condicional de Cores (Heatmap 2D)** ou o gráfico de linhas multissérie comparando os snapshots temporais (Atual, 1m, 3m, 1a atrás), que é o formato padrão utilizado por mesas de renda fixa institucionais.

### 4. Cálculo dinâmico em tempo real de p-valores da distribuição t de Student no DAX
- **Motivo**: O DAX não possui função nativa de distribuição $t$ de Student bicaudal com graus de liberdade flexíveis por filtro cruzado de evento.
- **Como é resolvido**: As bandas de confiança de 95% (`CAR_Lower_95`, `CAR_Upper_95`), a estatística $t$ e a significância já vêm pré-computadas na tabela `4_Event_Study_CAR.csv`.

---

## 4. Scripts de Importação Rápida no Power Query (M Code)

Para conectar o Power BI em menos de 1 minuto:
1. Abra o **Power BI Desktop**.
2. Vá em **Página Inicial** $\rightarrow$ **Transformar Dados** (Power Query).
3. Clique em **Novo Fonte** $\rightarrow$ **Pasta** $\rightarrow$ Selecione o caminho:
   `c:\Users\Marcos\Desktop\Brazilian Rates Intelligence\data\powerbi`
4. Ou adicione diretamente via **Consulta Nula** (`Editor Avançado`):

```powerquery
let
    CaminhoPasta = "c:\Users\Marcos\Desktop\Brazilian Rates Intelligence\data\powerbi\",
    FonteMacro = Csv.Document(File.Contents(CaminhoPasta & "1_Macro_Overview.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.None]),
    TabelaPromovida = Table.PromoteHeaders(FonteMacro, [PromoteAllScalars=true])
in
    TabelaPromovida
```

---

## 5. Medidas DAX Recomendadas

```dax
// 1. Selic Atual
Selic_Atual = 
CALCULATE(
    MAX('1_Macro_Overview'[Selic_Meta]),
    LASTNONBLANK('1_Macro_Overview'[Date], [Selic_Meta])
)

// 2. Rates Pressure Score Atual
Score_Atual = 
CALCULATE(
    LASTNONBLANKVALUE('6_Rates_Signal'[Date], SUM('6_Rates_Signal'[score]))
)

// 3. Status do Regime
Regime_Vigente = 
CALCULATE(
    LASTNONBLANKVALUE('3_Market_Regimes'[Date], SELECTEDVALUE('3_Market_Regimes'[Regime_Label]))
)

// 4. Slope da Curva (10Y - 2Y)
Slope_Atual = 
CALCULATE(
    LASTNONBLANKVALUE('2_Yield_Curve_TimeSeries'[Date], AVERAGE('2_Yield_Curve_TimeSeries'[Metric_Slope]))
)
```
