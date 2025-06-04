from flask import Flask, render_template, request, redirect, url_for, jsonify
import re
import sqlite3
from datetime import datetime


app = Flask(__name__)

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto TEXT,
            valor REAL,
            cliente TEXT,
            tipo TEXT,
            data TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS relatorios_encerrados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            vendas_avista REAL,
            vendas_fiado REAL,
            gastos REAL,
            lucro REAL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS gastos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT,
            valor REAL,
            data TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS chatbot_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pergunta TEXT,
            resposta TEXT,
            data TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/vendas', methods=['GET', 'POST'])
def venda():
    if request.method == 'POST':
        produto = request.form['produto']
        valor = float(request.form['valor'])
        cliente = request.form['cliente']
        tipo = request.form['tipo']
        data = datetime.now().strftime("%d-%m-%Y")
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO vendas (produto, valor, cliente, tipo, data) VALUES (?, ?, ?, ?, ?)',
                  (produto, valor, cliente, tipo, data))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
    return render_template('vendas.html')

@app.route('/gastos', methods=['GET', 'POST'])
def gasto():
    if request.method == 'POST':
        descricao = request.form['descricao']
        valor = float(request.form['valor'])
        data = datetime.now().strftime("%d-%m-%Y")
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT INTO gastos (descricao, valor, data) VALUES (?, ?, ?)',
                  (descricao, valor, data))
        conn.commit()
        conn.close()
        return redirect(url_for('home'))
    return render_template('gastos.html')

@app.route('/relatorio_dia')
def relatorio():
    data_hoje = datetime.now().strftime("%d-%m-%Y")
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    c.execute('SELECT * FROM vendas WHERE data = ?', (data_hoje,))
    vendas = c.fetchall()

    c.execute('SELECT * FROM gastos WHERE data = ?', (data_hoje,))
    gastos = c.fetchall()

    total_vendas = sum([v[2] for v in vendas if v[4].lower().replace(" ", "").replace("à", "a") == 'avista'])
    total_fiado = sum([v[2] for v in vendas if v[4].lower() == 'fiado'])
    total_gastos = sum([g[2] for g in gastos])
    lucro = (total_vendas + total_fiado) - total_gastos

    c.execute('''
        SELECT cliente, SUM(valor) 
        FROM vendas 
        WHERE tipo="fiado" AND data = ? 
        GROUP BY cliente
    ''', (data_hoje,))
    fiado_clientes = c.fetchall()

    conn.close()
    return render_template('relatorio_dia.html', total_vendas=total_vendas,
                           total_fiado=total_fiado, total_gastos=total_gastos,
                           lucro=lucro, fiado_clientes=fiado_clientes)

@app.route('/relatorios_finalizados')
def relatorios():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT data, vendas_avista, vendas_fiado, gastos, lucro FROM relatorios_encerrados ORDER BY data DESC')
    relatorios = c.fetchall()
    conn.close()
    return render_template('relatorios_finalizados.html', relatorios=relatorios)

@app.route('/historico_chat')
def historico_chat():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('SELECT pergunta, resposta, data FROM chatbot_logs ORDER BY id DESC')
    historico = c.fetchall()
    conn.close()
    return render_template('historico_chat.html', historico=historico)

@app.route('/chat', methods=['POST'])
def chat():
    import re
    user_message = request.json['pergunta'].lower()
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    data = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    response = None

    venda_match = re.search(
    r'registrar venda de (\d+(?:,\d+)?|\d+(?:\.\d+)?) reais (?:do produto|do|da|de|dos|das)?\s*([\w\sãáàâéêíóôõúç]+?) para (?:o |a )?(?:cliente )?([\w\sãáàâéêíóôõúç]+) (à vista|fiado)',
    user_message,
    flags=re.IGNORECASE
)


    if venda_match:
        valor = float(venda_match.group(1).replace(",", "."))
        produto = venda_match.group(2).strip().title()
        cliente = venda_match.group(3).strip().title()
        tipo = venda_match.group(4).strip().lower().replace(" ", "").replace("à", "a")
        
        c.execute('INSERT INTO vendas (produto, valor, cliente, tipo, data) VALUES (?, ?, ?, ?, ?)',
                (produto, valor, cliente, tipo, datetime.now().strftime("%d-%m-%Y")))
        conn.commit()
        response = f"✅ Venda registrada: R$ {valor:.2f} - Produto: {produto} - Cliente: {cliente} - Tipo: {tipo}."


    elif "registrar gasto" in user_message:
        gasto_match = re.search(r'registrar gasto de (\d+(?:,\d+)?|\d+(?:\.\d+)?) reais(?: com| em)? (.+)', user_message)
        if gasto_match:
            valor = float(gasto_match.group(1).replace(",", "."))
            descricao = gasto_match.group(2).strip()
            c.execute('INSERT INTO gastos (descricao, valor, data) VALUES (?, ?, ?)',
                      (descricao, valor, datetime.now().strftime("%d-%m-%Y")))
            conn.commit()
            response = f"✅ Gasto registrado: R$ {valor:.2f} - Descrição: {descricao}."
        else:
            response = "⚠️ Não consegui entender a descrição do gasto."
    elif "finalizar o dia" in user_message:
        hoje = datetime.now().strftime("%d-%m-%Y")
        hora = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        c.execute('SELECT SUM(valor) FROM vendas WHERE tipo="avista" AND data=?', (hoje,))
        avista = c.fetchone()[0] or 0
        c.execute('SELECT SUM(valor) FROM vendas WHERE tipo="fiado" AND data=?', (hoje,))
        fiado = c.fetchone()[0] or 0
        c.execute('SELECT SUM(valor) FROM gastos WHERE data=?', (hoje,))
        gastos = c.fetchone()[0] or 0
        lucro = (avista + fiado) - gastos

        c.execute('INSERT INTO relatorios_encerrados (data, vendas_avista, vendas_fiado, gastos, lucro) VALUES (?, ?, ?, ?, ?)',
                (hora, avista, fiado, gastos, lucro))

        response = (
            f"📦 Dia encerrado ({hoje})!\n"
            f"🟢 Vendas à vista: R$ {avista:.2f}\n"
            f"🟡 Vendas fiado: R$ {fiado:.2f}\n"
            f"🔴 Gastos: R$ {gastos:.2f}\n"
            f"💰 Lucro do dia: R$ {lucro:.2f}\n"
            f"Todos os registros do dia foram apagados do sistema."
        )

        conn.commit()
        c.execute('DELETE FROM vendas WHERE data=?', (hoje,))
        c.execute('DELETE FROM gastos WHERE data=?', (hoje,))
        conn.commit()
        
    else:
        response = (
            "🤖 Não entendi. Você pode dizer coisas como:\n"
            "- Registrar venda de 10 reais do produto pão para o cliente João à vista\n"
            "- Registrar gasto de 20 reais com energia\n"
            "- Relatório do dia\n"
            "- Finalizar o dia"
        )

    if response:
        c.execute('INSERT INTO chatbot_logs (pergunta, resposta, data) VALUES (?, ?, ?)',
                  (user_message, response, data))
        conn.commit()

    conn.close()
    return jsonify({'resposta': response})

@app.route('/ajuda')
def ajuda():
    return render_template('ajuda.html')

if __name__ == '__main__':
    app.run(debug=True)
