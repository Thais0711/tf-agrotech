from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import sqlite3, shutil, os
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "tf-agrotech-excluir-atualizado-2026"
DB_NAME = "banco.db"
BACKUP_DIR = "backups"

def conectar():
    banco = sqlite3.connect(DB_NAME)
    banco.row_factory = sqlite3.Row
    return banco

def criar_tabelas():
    banco = conectar()
    c = banco.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS propriedades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        cidade TEXT,
        estado TEXT,
        responsavel TEXT,
        telefone TEXT,
        criado_em TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        perfil TEXT NOT NULL,
        propriedade_id INTEGER,
        criado_em TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS animais (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        brinco TEXT NOT NULL,
        nome TEXT NOT NULL,
        categoria TEXT NOT NULL,
        raca TEXT,
        idade TEXT,
        peso REAL DEFAULT 0,
        vacina TEXT,
        criado_em TEXT,
        usuario_id INTEGER,
        propriedade_id INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS gastos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL,
        observacao TEXT,
        usuario_id INTEGER,
        propriedade_id INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS saidas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descricao TEXT NOT NULL,
        categoria TEXT NOT NULL,
        valor REAL NOT NULL,
        data TEXT NOT NULL,
        responsavel TEXT,
        observacao TEXT,
        usuario_id INTEGER,
        propriedade_id INTEGER
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS producao (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        litros REAL DEFAULT 0,
        animais_vendidos INTEGER DEFAULT 0,
        valor_recebido REAL DEFAULT 0,
        data TEXT NOT NULL,
        observacao TEXT,
        usuario_id INTEGER,
        propriedade_id INTEGER
    )""")

    admin = c.execute("SELECT id FROM usuarios WHERE email=?", ("admin@tfagrotech.com",)).fetchone()
    if not admin:
        c.execute("""INSERT INTO propriedades (nome,cidade,estado,responsavel,telefone,criado_em)
                     VALUES (?,?,?,?,?,?)""",
                  ("TF AgroTech Demonstração", "Sorriso", "MT", "Thais F da Silva Pereira", "",
                   datetime.now().strftime("%d/%m/%Y %H:%M")))
        prop_id = c.lastrowid
        c.execute("""INSERT INTO usuarios (nome,email,senha,perfil,propriedade_id,criado_em)
                     VALUES (?,?,?,?,?,?)""",
                  ("Thais F da Silva Pereira", "admin@tfagrotech.com", generate_password_hash("123456"),
                   "Administradora", prop_id, datetime.now().strftime("%d/%m/%Y %H:%M")))

    banco.commit()
    banco.close()

criar_tabelas()

def login_obrigatorio(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "usuario_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

def propriedade_atual():
    return session.get("propriedade_id")

def somente_admin():
    return session.get("usuario_perfil") == "Administradora"

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        senha = request.form.get("senha")

        banco = conectar()
        usuario = banco.execute("SELECT * FROM usuarios WHERE email=?", (email,)).fetchone()
        prop = None
        if usuario:
            prop = banco.execute("SELECT * FROM propriedades WHERE id=?", (usuario["propriedade_id"],)).fetchone()
        banco.close()

        if usuario and check_password_hash(usuario["senha"], senha):
            session["usuario_id"] = usuario["id"]
            session["usuario_nome"] = usuario["nome"]
            session["usuario_email"] = usuario["email"]
            session["usuario_perfil"] = usuario["perfil"]
            session["propriedade_id"] = usuario["propriedade_id"]
            session["propriedade_nome"] = prop["nome"] if prop else "Sem propriedade"
            return redirect(url_for("dashboard"))

        flash("E-mail ou senha incorretos.")
    return render_template("login.html")

@app.route("/criar_conta_fazenda", methods=["GET","POST"])
def criar_conta_fazenda():
    if request.method == "POST":
        banco = conectar()
        try:
            banco.execute("""INSERT INTO propriedades (nome,cidade,estado,responsavel,telefone,criado_em)
                             VALUES (?,?,?,?,?,?)""",
                          (request.form.get("nome_fazenda"), request.form.get("cidade"), request.form.get("estado"),
                           request.form.get("responsavel"), request.form.get("telefone"),
                           datetime.now().strftime("%d/%m/%Y %H:%M")))
            propriedade_id = banco.execute("SELECT last_insert_rowid()").fetchone()[0]

            banco.execute("""INSERT INTO usuarios (nome,email,senha,perfil,propriedade_id,criado_em)
                             VALUES (?,?,?,?,?,?)""",
                          (request.form.get("responsavel"), request.form.get("email"),
                           generate_password_hash(request.form.get("senha")),
                           "Administradora", propriedade_id,
                           datetime.now().strftime("%d/%m/%Y %H:%M")))
            banco.commit()
            banco.close()
            flash("Conta da fazenda criada com sucesso! Faça login.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            banco.close()
            flash("Esse e-mail já está cadastrado.")
            return redirect(url_for("criar_conta_fazenda"))

    return render_template("criar_conta_fazenda.html")

@app.route("/recuperar_senha", methods=["GET","POST"])
def recuperar_senha():
    if request.method == "POST":
        email = request.form.get("email")
        nova_senha = request.form.get("nova_senha")
        banco = conectar()
        usuario = banco.execute("SELECT * FROM usuarios WHERE email=?", (email,)).fetchone()
        if usuario:
            banco.execute("UPDATE usuarios SET senha=? WHERE email=?", (generate_password_hash(nova_senha), email))
            banco.commit()
            banco.close()
            flash("Senha alterada com sucesso. Faça login.")
            return redirect(url_for("login"))
        banco.close()
        flash("E-mail não encontrado.")
    return render_template("recuperar_senha.html")

@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_obrigatorio
def dashboard():
    pid = propriedade_atual()
    banco = conectar()
    c = banco.cursor()

    total_animais = c.execute("SELECT COUNT(*) FROM animais WHERE propriedade_id=?", (pid,)).fetchone()[0]
    total_gastos = c.execute("SELECT COALESCE(SUM(valor),0) FROM gastos WHERE propriedade_id=?", (pid,)).fetchone()[0]
    total_saidas = c.execute("SELECT COALESCE(SUM(valor),0) FROM saidas WHERE propriedade_id=?", (pid,)).fetchone()[0]
    total_litros = c.execute("SELECT COALESCE(SUM(litros),0) FROM producao WHERE propriedade_id=?", (pid,)).fetchone()[0]
    total_recebido = c.execute("SELECT COALESCE(SUM(valor_recebido),0) FROM producao WHERE propriedade_id=?", (pid,)).fetchone()[0]
    custo_total = total_gastos + total_saidas
    lucro = total_recebido - custo_total

    animais = c.execute("SELECT * FROM animais WHERE propriedade_id=? ORDER BY id DESC LIMIT 5", (pid,)).fetchall()
    gastos = c.execute("SELECT * FROM gastos WHERE propriedade_id=? ORDER BY id DESC LIMIT 5", (pid,)).fetchall()
    saidas = c.execute("SELECT * FROM saidas WHERE propriedade_id=? ORDER BY id DESC LIMIT 5", (pid,)).fetchall()

    banco.close()
    return render_template("index.html", total_animais=total_animais, total_gastos=total_gastos,
                           total_saidas=total_saidas, custo_total=custo_total, total_litros=total_litros,
                           total_recebido=total_recebido, lucro=lucro, animais=animais, gastos=gastos, saidas=saidas)

@app.route("/cadastro_usuario", methods=["GET","POST"])
@login_obrigatorio
def cadastro_usuario():
    pid = propriedade_atual()
    if not somente_admin():
        flash("Apenas administradores podem criar usuários.")
        return redirect(url_for("usuarios"))

    if request.method == "POST":
        banco = conectar()
        try:
            banco.execute("""INSERT INTO usuarios (nome,email,senha,perfil,propriedade_id,criado_em)
                             VALUES (?,?,?,?,?,?)""",
                          (request.form.get("nome"), request.form.get("email"),
                           generate_password_hash(request.form.get("senha")),
                           request.form.get("perfil"), pid, datetime.now().strftime("%d/%m/%Y %H:%M")))
            banco.commit()
            banco.close()
            flash("Usuário da fazenda criado com sucesso.")
            return redirect(url_for("usuarios"))
        except sqlite3.IntegrityError:
            banco.close()
            flash("Esse e-mail já existe.")
    return render_template("cadastro_usuario.html")

@app.route("/usuarios")
@login_obrigatorio
def usuarios():
    banco = conectar()
    usuarios = banco.execute("SELECT * FROM usuarios WHERE propriedade_id=? ORDER BY id DESC", (propriedade_atual(),)).fetchall()
    banco.close()
    return render_template("usuarios.html", usuarios=usuarios)

@app.route("/excluir_usuario/<int:id>")
@login_obrigatorio
def excluir_usuario(id):
    if not somente_admin():
        flash("Apenas administradores podem excluir usuários.")
        return redirect(url_for("usuarios"))

    if id == session.get("usuario_id"):
        flash("Você não pode excluir o próprio usuário logado.")
        return redirect(url_for("usuarios"))

    banco = conectar()
    banco.execute("DELETE FROM usuarios WHERE id=? AND propriedade_id=?", (id, propriedade_atual()))
    banco.commit()
    banco.close()
    flash("Usuário excluído com sucesso.")
    return redirect(url_for("usuarios"))

@app.route("/propriedade")
@login_obrigatorio
def propriedade():
    banco = conectar()
    prop = banco.execute("SELECT * FROM propriedades WHERE id=?", (propriedade_atual(),)).fetchone()
    banco.close()
    return render_template("propriedade.html", propriedade=prop)

@app.route("/rebanho", methods=["GET","POST"])
@login_obrigatorio
def rebanho():
    pid = propriedade_atual()
    banco = conectar()
    if request.method == "POST":
        banco.execute("""INSERT INTO animais (brinco,nome,categoria,raca,idade,peso,vacina,criado_em,usuario_id,propriedade_id)
                         VALUES (?,?,?,?,?,?,?,?,?,?)""",
                      (request.form.get("brinco"), request.form.get("nome"), request.form.get("categoria"),
                       request.form.get("raca"), request.form.get("idade"), request.form.get("peso") or 0,
                       request.form.get("vacina"), datetime.now().strftime("%d/%m/%Y %H:%M"),
                       session.get("usuario_id"), pid))
        banco.commit()
        banco.close()
        return redirect(url_for("rebanho"))
    animais = banco.execute("SELECT * FROM animais WHERE propriedade_id=? ORDER BY id DESC", (pid,)).fetchall()
    banco.close()
    return render_template("rebanho.html", animais=animais)

@app.route("/excluir_animal/<int:id>")
@login_obrigatorio
def excluir_animal(id):
    banco = conectar()
    banco.execute("DELETE FROM animais WHERE id=? AND propriedade_id=?", (id, propriedade_atual()))
    banco.commit()
    banco.close()
    return redirect(url_for("rebanho"))

@app.route("/gastos", methods=["GET","POST"])
@login_obrigatorio
def gastos():
    pid = propriedade_atual()
    banco = conectar()
    if request.method == "POST":
        banco.execute("""INSERT INTO gastos (tipo,valor,data,observacao,usuario_id,propriedade_id)
                         VALUES (?,?,?,?,?,?)""",
                      (request.form.get("tipo"), request.form.get("valor") or 0, request.form.get("data"),
                       request.form.get("observacao"), session.get("usuario_id"), pid))
        banco.commit()
        banco.close()
        return redirect(url_for("gastos"))
    gastos = banco.execute("SELECT * FROM gastos WHERE propriedade_id=? ORDER BY id DESC", (pid,)).fetchall()
    total_gastos = banco.execute("SELECT COALESCE(SUM(valor),0) FROM gastos WHERE propriedade_id=?", (pid,)).fetchone()[0]
    banco.close()
    return render_template("gastos.html", gastos=gastos, total_gastos=total_gastos)

@app.route("/excluir_gasto/<int:id>")
@login_obrigatorio
def excluir_gasto(id):
    banco = conectar()
    banco.execute("DELETE FROM gastos WHERE id=? AND propriedade_id=?", (id, propriedade_atual()))
    banco.commit()
    banco.close()
    return redirect(url_for("gastos"))

@app.route("/saidas", methods=["GET","POST"])
@login_obrigatorio
def saidas():
    pid = propriedade_atual()
    banco = conectar()
    if request.method == "POST":
        banco.execute("""INSERT INTO saidas (descricao,categoria,valor,data,responsavel,observacao,usuario_id,propriedade_id)
                         VALUES (?,?,?,?,?,?,?,?)""",
                      (request.form.get("descricao"), request.form.get("categoria"), request.form.get("valor") or 0,
                       request.form.get("data"), request.form.get("responsavel"), request.form.get("observacao"),
                       session.get("usuario_id"), pid))
        banco.commit()
        banco.close()
        return redirect(url_for("saidas"))
    saidas = banco.execute("SELECT * FROM saidas WHERE propriedade_id=? ORDER BY id DESC", (pid,)).fetchall()
    total_saidas = banco.execute("SELECT COALESCE(SUM(valor),0) FROM saidas WHERE propriedade_id=?", (pid,)).fetchone()[0]
    banco.close()
    return render_template("saidas.html", saidas=saidas, total_saidas=total_saidas)

@app.route("/excluir_saida/<int:id>")
@login_obrigatorio
def excluir_saida(id):
    banco = conectar()
    banco.execute("DELETE FROM saidas WHERE id=? AND propriedade_id=?", (id, propriedade_atual()))
    banco.commit()
    banco.close()
    return redirect(url_for("saidas"))

@app.route("/producao", methods=["GET","POST"])
@login_obrigatorio
def producao():
    pid = propriedade_atual()
    banco = conectar()
    if request.method == "POST":
        banco.execute("""INSERT INTO producao (litros,animais_vendidos,valor_recebido,data,observacao,usuario_id,propriedade_id)
                         VALUES (?,?,?,?,?,?,?)""",
                      (request.form.get("litros") or 0, request.form.get("animais_vendidos") or 0,
                       request.form.get("valor_recebido") or 0, request.form.get("data"),
                       request.form.get("observacao"), session.get("usuario_id"), pid))
        banco.commit()
        banco.close()
        return redirect(url_for("producao"))
    producoes = banco.execute("SELECT * FROM producao WHERE propriedade_id=? ORDER BY id DESC", (pid,)).fetchall()
    banco.close()
    return render_template("producao.html", producoes=producoes)

@app.route("/excluir_producao/<int:id>")
@login_obrigatorio
def excluir_producao(id):
    banco = conectar()
    banco.execute("DELETE FROM producao WHERE id=? AND propriedade_id=?", (id, propriedade_atual()))
    banco.commit()
    banco.close()
    return redirect(url_for("producao"))

@app.route("/relatorios")
@login_obrigatorio
def relatorios():
    pid = propriedade_atual()
    banco = conectar()
    c = banco.cursor()
    total_animais = c.execute("SELECT COUNT(*) FROM animais WHERE propriedade_id=?", (pid,)).fetchone()[0]
    total_gastos = c.execute("SELECT COALESCE(SUM(valor),0) FROM gastos WHERE propriedade_id=?", (pid,)).fetchone()[0]
    total_saidas = c.execute("SELECT COALESCE(SUM(valor),0) FROM saidas WHERE propriedade_id=?", (pid,)).fetchone()[0]
    total_litros = c.execute("SELECT COALESCE(SUM(litros),0) FROM producao WHERE propriedade_id=?", (pid,)).fetchone()[0]
    total_recebido = c.execute("SELECT COALESCE(SUM(valor_recebido),0) FROM producao WHERE propriedade_id=?", (pid,)).fetchone()[0]
    custo_total = total_gastos + total_saidas
    lucro = total_recebido - custo_total
    banco.close()
    return render_template("relatorios.html", total_animais=total_animais, total_gastos=total_gastos,
                           total_saidas=total_saidas, custo_total=custo_total, total_litros=total_litros,
                           total_recebido=total_recebido, lucro=lucro)

@app.route("/backup")
@login_obrigatorio
def backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    nome = f"backup_tf_agrotech_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    caminho = os.path.join(BACKUP_DIR, nome)
    shutil.copy(DB_NAME, caminho)
    return send_file(caminho, as_attachment=True, download_name=nome)

if __name__ == "__main__":
    app.run(debug=True)
