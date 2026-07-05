import streamlit as st
import pandas as pd
import os
import re
from datetime import datetime
import plotly.express as px

st.set_page_config(page_title="CRBU PCBA Tracker", layout="wide")
st.title("📊 CRBU Bonepile Executive Dashboard (PCBA Division)")

# --- CARGAR HISTORIAL DESDE EL ARCHIVO SI EXISTE ---
HISTORIC_FILE = "bonepile_history.csv"

if os.path.exists(HISTORIC_FILE):
    try:
        df_historico_master = pd.read_csv(HISTORIC_FILE)
    except:
        df_historico_master = pd.DataFrame(columns=["Fecha", "Total_Units", "Avg_Aging_Days", "Critical_Units_120", "Total_Risk_USD"])
else:
    df_historico_master = pd.DataFrame(columns=["Fecha", "Total_Units", "Avg_Aging_Days", "Critical_Units_120", "Total_Risk_USD"])

st.sidebar.header("📁 Panel de Control")
uploaded_file = st.sidebar.file_uploader("Arrastra el reporte Excel diario aquí", type=["xlsx"])

if uploaded_file:
    file_name = uploaded_file.name
    date_match = re.search(r'(\d{2})-(\d{2})-(\d{4})', file_name)
    fecha_reporte = f"{date_match.group(3)}-{date_match.group(1)}-{date_match.group(2)}" if date_match else datetime.today().strftime('%Y-%m-%d')
    
    xls = pd.ExcelFile(uploaded_file)
    df_bp = pd.read_excel(xls, sheet_name="BP")
    df_bp = df_bp[(df_bp["business_unit"] == "CRBU") & (~df_bp["area"].astype(str).str.startswith("SYS"))]
    
    try:
        df_entry = pd.read_excel(xls, sheet_name="BP_ENTRY")
        df_entry = df_entry[(df_entry["business_unit"] == "CRBU") & (~df_entry["area"].astype(str).str.startswith("SYS"))]
        entries_count = len(df_entry)
    except:
        entries_count = 0
        
    try:
        df_exit = pd.read_excel(xls, sheet_name="BP_EXIT")
        df_exit = df_exit[(df_exit["business_unit"] == "CRBU") & (~df_exit["area"].astype(str).str.startswith("SYS"))]
        exits_count = len(df_exit)
    except:
        exits_count = 0

    total_units = len(df_bp)
    avg_aging = round(df_bp["bonepile_aging_days"].mean(), 1) if total_units > 0 else 0.0
    total_cost = round(df_bp["quoted_cost"].sum(), 2) if total_units > 0 else 0.0
    throughput = round((exits_count / entries_count), 3) if entries_count > 0 else 0.0
    
    df_critical = df_bp[df_bp["bonepile_aging_days"] > 120]
    critical_count = len(df_critical)
    critical_cost = round(df_critical["quoted_cost"].sum(), 2)

    # --- GUARDADO SEGURO E HISTORIAL ACUMULATIVO ---
    new_row = pd.DataFrame([{
        "Fecha": fecha_reporte,
        "Total_Units": total_units,
        "Avg_Aging_Days": avg_aging,
        "Critical_Units_120": critical_count,
        "Total_Risk_USD": total_cost
    }])
    
    # Unir datos nuevos con el archivo viejo evitando duplicar el mismo día
    if not df_historico_master.empty:
        df_historico_master = df_historico_master[df_historico_master["Fecha"] != fecha_reporte]
    
    df_historico_master = pd.concat([df_historico_master, new_row], ignore_index=True).sort_values("Fecha").reset_index(drop=True)
    df_historico_master.to_csv(HISTORIC_FILE, index=False)

    st.subheader(f"📍 Análisis del Reporte Diario: {fecha_reporte}")
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Active Units (PCBA)", f"{total_units:,}")
    kpi2.metric("Average Aging", f"{avg_aging} días")
    kpi3.metric("Throughput Efficiency", f"{throughput*100:.1f}%")
    kpi4.metric("Total Risk Value", f"${total_cost:,.2f}")

    st.markdown("---")
    st.markdown("### 🚨 Zona de Riesgo Crítico (> 120 Días Target Cliente)")
    
    crit1, crit2 = st.columns(2)
    crit1.info(f"🛑 **Unidades en Infracción:** {critical_count} piezas superan el límite del cliente.")
    crit2.error(f"💰 **Impacto en Riesgo Financiero:** ${critical_cost:,.2f} USD retenidos en material crítico.")

    st.markdown("---")
    st.subheader("📋 Consola de Operaciones y Seguimiento Diario")
    st.write("Modifica el estatus de las unidades directamente en la columna 'Estatus Operacional' para la junta diaria:")

    df_operaciones = df_bp[["sernum", "area", "product_family", "bonepile_aging_days", "quoted_cost"]].copy()
    df_operaciones = df_operaciones.sort_values(by="bonepile_aging_days", ascending=False).reset_index(drop=True)
    df_operaciones["Estatus Operacional"] = "Pendiente de Revision"

    df_editado = st.data_editor(
        df_operaciones,
        column_config={
            "Estatus Operacional": st.column_config.SelectboxColumn(
                "Estatus Operacional",
                options=["Pendiente de Revision", "En Falla / Link Error", "Pendiente de Prueba", "En Reparacion", "Liberado / Scrap Realizado"],
                required=True
            )
        },
        disabled=["sernum", "area", "product_family", "bonepile_aging_days", "quoted_cost"],
        use_container_width=True
    )

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        df_pareto = df_editado.groupby("Estatus Operacional").size().reset_index(name="Cantidad").sort_values(by="Cantidad", ascending=False)
        fig_pareto = px.bar(df_pareto, x="Estatus Operacional", y="Cantidad", title="Pareto de Distribución por Estatus de Falla", text_auto=True)
        st.plotly_chart(fig_pareto, use_container_width=True)

    with col_chart2:
        st.write("### 📤 Exportar Resultados")
        st.write("Genera el archivo consolidado con los comentarios asignados por tu equipo:")
        csv_buffer = df_editado.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="💾 Descargar Reporte Operacional (.CSV)",
            data=csv_buffer,
            file_name=f"Reporte_CRBU_Operaciones_{fecha_reporte}.csv",
            mime="text/csv"
        )

# --- MOSTRAR TENDENCIAS HISTÓRICAS SIEMPRE AL FONDO ---
st.markdown("---")
st.subheader("📈 Tendencias e Historial Acumulado Semestral")

if not df_historico_master.empty:
    fig_line_units = px.line(df_historico_master, x="Fecha", y=["Total_Units", "Critical_Units_120"], title="Evolución del Backlog (Total vs >120 Días)", markers=True)
    fig_line_cost = px.line(df_historico_master, x="Fecha", y="Total_Risk_USD", title="Tendencia del Valor Financiero en Riesgo ($ USD)", markers=True)
    
    t_col1, t_col2 = st.columns(2)
    t_col1.plotly_chart(fig_line_units, use_container_width=True)
    t_col2.plotly_chart(fig_line_cost, use_container_width=True)
else:
    st.info("💡 Sube tu primer archivo Excel en la barra lateral para comenzar a trazar las líneas de tendencia.")
