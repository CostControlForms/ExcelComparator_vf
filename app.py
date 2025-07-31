from flask import Flask, render_template, request
import pandas as pd
import os

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        file1 = request.files["file1"]
        file2 = request.files["file2"]

        path1 = os.path.join(UPLOAD_FOLDER, file1.filename)
        path2 = os.path.join(UPLOAD_FOLDER, file2.filename)

        file1.save(path1)
        file2.save(path2)

        df1 = pd.read_excel(path1)
        df2 = pd.read_excel(path2)

        diferencias = []
        if df1.shape == df2.shape:
            for i in range(df1.shape[0]):
                for j in range(df1.shape[1]):
                    val1 = df1.iat[i, j]
                    val2 = df2.iat[i, j]
                    if pd.isna(val1) and pd.isna(val2):
                        continue
                    if val1 != val2:
                        diferencias.append({
                            "Fila": i + 1,
                            "Columna": df1.columns[j],
                            "Valor 1": val1,
                            "Valor 2": val2
                        })
        else:
            return render_template("resultado.html", diferencias=None, error="The files do not have the same structure")

        return render_template("resultado.html", diferencias=diferencias, error=None)
    return render_template("index.html")

if __name__ == "__main__":
    app.run(debug=True)

