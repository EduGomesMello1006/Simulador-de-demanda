
from flask import Flask, render_template, request, jsonify, send_file
import sqlite3
from fpdf import FPDF
import base64
from io import BytesIO
import tempfile

app = Flask(__name__)

def gerar_pdf_com_graficos(equipamentos, graficos, consumo_mes, economia=None, tarifa_pais="brasil", potencia_contratada=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(190, 10, txt="Relatório de Consumo de Energia", ln=True, align="C")
    pdf.ln(10)

    pdf.set_font("Arial", 'B', 11)
    pdf.cell(60, 10, "Equipamento", 1)
    pdf.cell(30, 10, "Potência (W)", 1)
    pdf.cell(40, 10, "Tipo", 1)
    pdf.cell(30, 10, "Qtd", 1)
    pdf.ln()

    pdf.set_font("Arial", '', 11)
    for eq in equipamentos:
        pdf.cell(60, 10, eq['nome'], 1)
        pdf.cell(30, 10, str(eq['potencia']), 1)
        pdf.cell(40, 10, eq['tipoEquipamento'], 1)
        pdf.cell(30, 10, str(eq['quantidade']), 1)
        pdf.ln()

    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "Gráficos Gerais:", ln=True)
    pdf.ln(5)

    for nome in ['graficoHora', 'graficoMes']:
        base64_str = graficos.get(nome)
        if base64_str and base64_str.startswith("data:image"):
            header, encoded = base64_str.split(",", 1)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                tmp_img.write(base64.b64decode(encoded))
                tmp_img.flush()
                pdf.image(tmp_img.name, w=180)
                pdf.ln(5)

    pdf.ln(10)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(190, 10, "a) Gráficos por Tipo de Carga", ln=True)
    pdf.ln(5)

    tipos = [
        ('iluminacao', 'Iluminação'),
        ('tue', 'TUE (Tomada de Uso Específico)'),
        ('tug', 'TUG (Tomada de Uso Geral)')
    ]

    for chave, titulo in tipos:
        base64_str = graficos.get(chave)
        if base64_str and base64_str.startswith("data:image"):
            try:
                header, encoded = base64_str.split(",", 1)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_img:
                    tmp_img.write(base64.b64decode(encoded))
                    tmp_img.flush()
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(190, 10, titulo, ln=True)
                    pdf.image(tmp_img.name, w=180)
                    pdf.ln(5)
            except Exception as e:
                print(f"[ERRO] Falha ao inserir gráfico '{chave}': {e}")

    consumo_total = sum(consumo_mes)
    tarifa_kwh = 0.6369
    valor_fatura = 0

    if tarifa_pais == "portugal":
        tarifas_potencia = {
            "sem potencia contratada fixa": 0.0460,
            "1.15": 0.0529,
            "2.3": 0.1058,
            "3.45": 0.1587,
            "4.6": 0.2116,
            "5.75": 0.2645,
            "6.9": 0.3174,
            "10.35": 0.4761,
            "13.8": 0.6348,
            "17.25": 0.7935,
            "20.7": 0.9522
        }

        tarifa_energia_simples = 0.0600
        tarifa_bi = {"vazio": 0.0149, "fora": 0.0830}
        tarifa_tri = {"vazio": 0.0149, "cheias": 0.0388, "ponta": 0.2496}

        horas_vazio_bi = list(range(0, 8)) + list(range(22, 24))
        horas_ponta_tri = [8, 9, 18, 19, 20]
        horas_cheias_tri = list(range(9, 18)) + [20, 21]
        horas_vazio_tri = list(range(0, 8)) + list(range(22, 24))

        total_vazio_bi = total_fora_bi = 0
        total_ponta_tri = total_cheias_tri = total_vazio_tri = 0

        for i, kwh in enumerate(consumo_mes[:24]):
            if i in horas_vazio_bi:
                total_vazio_bi += kwh
            else:
                total_fora_bi += kwh

            if i in horas_ponta_tri:
                total_ponta_tri += kwh
            elif i in horas_cheias_tri:
                total_cheias_tri += kwh
            else:
                total_vazio_tri += kwh

        custo_fixo_mensal = tarifas_potencia.get(str(potencia_contratada), 0.1587) * 30
        custo_simples = consumo_total * tarifa_energia_simples + custo_fixo_mensal
        custo_bi = total_vazio_bi * tarifa_bi['vazio'] + total_fora_bi * tarifa_bi['fora'] + custo_fixo_mensal
        custo_tri = total_vazio_tri * tarifa_tri['vazio'] + total_cheias_tri * tarifa_tri['cheias'] + total_ponta_tri * tarifa_tri['ponta'] + custo_fixo_mensal

        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 10, "b) Simulação Tarifária - Portugal (Inverno)", ln=True)
        pdf.set_font("Arial", '', 11)
        pdf.cell(190, 10, f"Tarifa Simples: EUR {custo_simples:.2f}", ln=True)
        pdf.cell(190, 10, f"Tarifa Bi-horária: EUR {custo_bi:.2f}", ln=True)
        pdf.cell(190, 10, f"Tarifa Tri-horária (Inverno): EUR {custo_tri:.2f}", ln=True)

        valor_fatura = custo_simples
        tarifa_kwh = tarifa_energia_simples

    else:
        tarifa_total_mwh = 373.17 + 263.07
        tarifa_kwh = tarifa_total_mwh / 1000
        valor_fatura = consumo_total * tarifa_kwh

        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 10, "b) Simulação Tarifária - Brasil", ln=True)
        pdf.set_font("Arial", '', 11)
        pdf.cell(190, 10, f"Tarifa Média Aplicada: R$ {tarifa_kwh:.5f}", ln=True)
        pdf.cell(190, 10, f"Valor Estimado da Fatura: R$ {valor_fatura:.2f}", ln=True)

    if economia:
        pdf.ln(10)
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 10, "c) Economia Estimada com Tomada Inteligente", ln=True)
        pdf.set_font("Arial", '', 11)
        pdf.cell(190, 10, f"Consumo informado na conta: {economia.get('consumoConta', '---')} kWh", ln=True)
        pdf.cell(190, 10, f"Economia estimada: {economia.get('economiaKWh', '---')} kWh", ln=True)
        pdf.cell(190, 10, f"Novo consumo após otimização: {economia.get('novoConsumo', '---')} kWh", ln=True)
        pdf.cell(190, 10, f"Redução percentual: {economia.get('percentualReducao', '---')}%", ln=True)

    output = BytesIO()
    output.write(pdf.output(dest='S').encode('latin-1'))
    output.seek(0)
    return output

@app.route('/gerar-pdf', methods=['POST'])
def gerar_pdf():
    dados = request.get_json()
    equipamentos = dados.get('equipamentos', [])
    graficos = dados.get('graficos', {})
    consumo_mes = dados.get('consumoMes', [])
    economia = dados.get('economia', {})
    tarifa_pais = dados.get("tarifaPais", "brasil")
    potencia_contratada = dados.get("potenciaContratada")
    pdf_output = gerar_pdf_com_graficos(equipamentos, graficos, consumo_mes, economia, tarifa_pais, potencia_contratada)
    return send_file(pdf_output, download_name="relatorio_consumo.pdf", as_attachment=True)

@app.route('/')
def index():
    conn = sqlite3.connect('equipamentos.db')
    c = conn.cursor()
    c.execute("SELECT nome, potencia FROM equipamentos")
    equipamentos = c.fetchall()
    conn.close()
    return render_template('index.html', equipamentos=equipamentos)

@app.route('/adicionar', methods=['POST'])
def adicionar():
    dados = request.get_json()
    nome = dados['nome']
    potencia = float(dados['potencia'])
    conn = sqlite3.connect('equipamentos.db')
    c = conn.cursor()
    c.execute('INSERT INTO equipamentos (nome, potencia) VALUES (?, ?)', (nome, potencia))
    conn.commit()
    conn.close()
    return jsonify({'mensagem': 'Equipamento adicionado com sucesso'})

@app.route('/equipamentos')
def listar():
    conn = sqlite3.connect('equipamentos.db')
    c = conn.cursor()
    c.execute('SELECT nome, potencia FROM equipamentos')
    dados = c.fetchall()
    conn.close()
    return jsonify(dados)

@app.route('/excluir', methods=['POST'])
def excluir():
    dados = request.get_json()
    nome = dados['nome']
    senha = dados['senha']
    if senha != '1234':
        return jsonify({'erro': 'Acesso negado'}), 403
    conn = sqlite3.connect('equipamentos.db')
    c = conn.cursor()
    c.execute('DELETE FROM equipamentos WHERE nome = ?', (nome,))
    conn.commit()
    conn.close()
    return jsonify({'mensagem': f'"{nome}" excluído com sucesso'})

def init_db():
    conn = sqlite3.connect('equipamentos.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS equipamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            potencia REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_db()