from flask import Flask, render_template, request, send_file, abort, url_for
import pandas as pd
import os
from pathlib import Path
from werkzeug.utils import secure_filename
from uuid import uuid4
from io import BytesIO
DIFF_CACHE = {}

app = Flask(__name__, template_folder="templates", static_folder="static")

# ===== Config =====
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Sólo permitimos Excel
ALLOWED_EXTENSIONS = {".xls", ".xlsx"}

def allowed_file(name: str) -> bool:
    return Path(name).suffix.lower() in ALLOWED_EXTENSIONS

# Cache en memoria para descargas (token -> dict con bytes y metadatos)
DIFF_CACHE = {}  # { token: {"bytes": b"...", "mimetype": "...", "filename": "..."} }


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file1 = request.files.get("file1")
        file2 = request.files.get("file2")

        # Comprobación básica
        if not file1 or not file2 or file1.filename == "" or file2.filename == "":
            return render_template("resultado.html",
                                   diferencias=None,
                                   error="Please select both files.",
                                   ok=None,
                                   download_url="")

        # ⛔ Validación de tipo ANTES de guardar/leer
        if not (allowed_file(file1.filename) and allowed_file(file2.filename)):
            return render_template("resultado.html",
                                   diferencias=None,
                                   error="Only Excel files (.xls, .xlsx) are allowed.",
                                   ok=None,
                                   download_url="")

        # Guardar con nombres seguros (opcional)
        f1name = secure_filename(file1.filename)
        f2name = secure_filename(file2.filename)
        path1 = os.path.join(UPLOAD_FOLDER, f1name)
        path2 = os.path.join(UPLOAD_FOLDER, f2name)
        file1.lsve(path1)
        file2.save(path2)

        # Leer
        try:
            df1 = pd.read_excel(path1)
            df2 = pd.read_excel(path2)
        except Exception as e:
            return render_template("resultado.html",
                                   diferencias=None,
                                   error=f"Error reading files: {e}",
                                   ok=None,
                                   download_url="")

        # Validación de formato mínimo (mismo nº de filas y columnas)
        if df1.shape != df2.shape:
            return render_template("resultado.html",
                                   diferencias=None,
                                   error="Different format of Excels (rows/columns mismatch).",
                                   ok=None,
                                   download_url="")

        # Comparación celda a celda
        diferencias = []
        rows, cols = df1.shape
        for i in range(rows):
            for j in range(cols):
                v1 = df1.iat[i, j]
                v2 = df2.iat[i, j]
                # NaN ~ NaN
                if (pd.isna(v1) and pd.isna(v2)) or (v1 == v2):
                    continue
                diferencias.append({
                    "Fila": i + 1,
                    "Columna": str(df1.columns[j]),
                    "Valor 1": v1,
                    "Valor 2": v2
                })

        # Sin diferencias
        if not diferencias:
            return render_template("resultado.html",
                                   diferencias=None,
                                   error=None,
                                   ok="Not differences found",
                                   download_url="")

        # ===== Generar archivo para descargar EN MEMORIA =====
        df_diff = pd.DataFrame(diferencias, columns=["Fila", "Columna", "Valor 1", "Valor 2"])
        token = uuid4().hex

        # Intentamos XLSX; si no hay motor, caemos a CSV
        file_bytes = BytesIO()
        mimetype = ""
        download_name = ""
        try:
            # Preferimos openpyxl; si no, probamos xlsxwriter
            try:
                with pd.ExcelWriter(file_bytes, engine="openpyxl") as writer:
                    df_diff.to_excel(writer, index=False, sheet_name="Differences")
            except Exception:
                with pd.ExcelWriter(file_bytes, engine="xlsxwriter") as writer:
                    df_diff.to_excel(writer, index=False, sheet_name="Differences")
            file_bytes.seek(0)
            mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            download_name = "differences.xlsx"
        except Exception:
            # Fallback CSV
            file_bytes = BytesIO()
            df_diff.to_csv(file_bytes, index=False)
            file_bytes.seek(0)
            mimetype = "text/csv"
            download_name = "differences.csv"

        # Guardamos en cache en memoria
        DIFF_CACHE[token] = {
            "bytes": file_bytes.getvalue(),
            "mimetype": mimetype,
            "filename": download_name
        }
        download_url = url_for("download", token=token)

        return render_template("resultado.html",
                               diferencias=diferencias,
                               error=None,
                               ok=None,
                               download_url=download_url)

    # GET
    return render_template("index.html")


@app.route("/download/<token>")
def download(token: str):
    # Recuperamos el archivo de la cache
    data = DIFF_CACHE.get(token)
    if not data:
        abort(404)
    return send_file(BytesIO(data["bytes"]),
                     as_attachment=True,
                     download_name=data["filename"],
                     mimetype=data["mimetype"])


if __name__ == "__main__":
    # Debug para ver trazas si algo fallara
    app.run(host="0.0.0.0", port=5000, debug=True)

