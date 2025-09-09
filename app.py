import os
import psycopg2
import pandas as pd
from dotenv import load_dotenv

from dash import Dash, dcc, html, dash_table
import dash_bootstrap_components as dbc

import plotly.express as px

import numpy as np
from scipy.stats import gaussian_kde


# Load environment variables for database conn
load_dotenv()
dbname = os.getenv("POSTGRES_DBNAME")
hostname = os.getenv("POSTGRES_HOST")
port = os.getenv("POSTGRES_PORT")
user = os.getenv("POSTGRES_USER")
pword = os.getenv("POSTGRES_PASSWORD")

# connects to db, loads query result into dataframe
def get_data(query):
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=pword,
        host=hostname,
        port=port
    )
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# generate plots
# create a bar chart with pass/fail % grouped by parameter
query = """
SELECT 
    parameter,
    pass_fail,
    100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY parameter) AS percent
FROM wafer_probe_results
GROUP BY parameter, pass_fail
ORDER BY parameter, pass_fail;
"""
df = get_data(query)

# plot bar chart grouped on pass/fail %
# Plot grouped bar chart
fig_bar = px.bar(
    df,
    x="parameter",
    y="percent",
    color="pass_fail",
    barmode="group",
    text="percent",
    labels={"percent": "Percentage (%)", "parameter": "Parameter", "pass_fail": "Result"},
    title="Pass/Fail Percentage by Parameter"
)

fig_bar.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
fig_bar.update_layout(yaxis=dict(range=[0, 100]))


# plot the volume of tests overtime
query = """
    SELECT DATE(timestamp) AS day, COUNT(id) AS total_tests
    FROM wafer_probe_results
    GROUP BY DATE(timestamp)
    ORDER BY day;
"""
df = get_data(query)
fig_ts = px.line(df, x="day", y="total_tests", markers=True,
              title="Total Tests per Day")


# histogram - TODO: remove filter when interative filters added
query = """
SELECT measured_value
FROM wafer_probe_results
WHERE measured_value IS NOT NULL
AND parameter = 'Vth';
"""
df = get_data(query)

fig_hist = px.histogram(
    df,
    x="measured_value",
    nbins=50,
    marginal=None,
    opacity=0.7,
    title="Distribution of Measured Values"
)

values = df['measured_value'].values
kde = gaussian_kde(values)
x_range = np.linspace(values.min(), values.max(), 500)
fig_hist.add_scatter(
    x=x_range,
    y=kde(x_range) * len(values) * (values.max()-values.min())/50,  # scale to histogram
    mode='lines',
    line=dict(color='red', width=2),
    name='KDE'
)

fig_hist.update_layout(
    xaxis_title="Measured Value",
    yaxis_title="Count"
)

# --- summary ---
query = """
SELECT 
    COUNT(id) AS total_dies,
    COUNT(DISTINCT (wafer_id, lot_id)) AS total_wafers,
    COUNT(DISTINCT lot_id) AS total_lots,
    100.0 * SUM(CASE WHEN pass_fail = 'PASS' THEN 1 ELSE 0 END) / COUNT(*) AS yield_percent
FROM wafer_probe_results;
"""
df_kpi = get_data(query).iloc[0]

kpi_cards = dbc.Row(
    [
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H2(f"{df_kpi['total_dies']:,}", className="card-title text-center"),
                    html.P("Dies", className="text-center")
                ])
            ),
            md=3
        ),
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H2(f"{df_kpi['total_wafers']:,}", className="card-title text-center"),
                    html.P("Wafers", className="text-center")
                ])
            ),
            md=3
        ),
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H2(f"{df_kpi['total_lots']:,}", className="card-title text-center"),
                    html.P("Lots", className="text-center")
                ])
            ),
            md=3
        ),
        dbc.Col(
            dbc.Card(
                dbc.CardBody([
                    html.H2(f"{df_kpi['yield_percent']:.1f}%", className="card-title text-center text-success"),
                    html.P("Yield", className="text-center")
                ])
            ),
            md=3
        )
    ],
    className="mb-4"
)

# Initialize Dash app
app = Dash(__name__)

# use a bootstrap theme
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

def serve_layout():
    layout = dbc.Container(
        fluid=True,
        children=[
            dbc.Row(
                dbc.Col(
                    html.H1("Product Testing Results", className="text-center my-4"),
                    width=12
                )
            ),

            # KPI cards row
            kpi_cards,

            # Charts row
            dbc.Row(
                [
                    dbc.Col(dcc.Graph(figure=fig_ts), md=6),
                    dbc.Col(dcc.Graph(figure=fig_bar), md=6),
                ],
                className="mb-4"
            ),

            # histogram chart row
            dbc.Row(
                dbc.Col(dcc.Graph(figure=fig_hist), width=6),
                className="mb-4 justify-content-center"
            ),
        ]
    )

    return layout

# layout
app.layout = serve_layout()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=True)

    # test
