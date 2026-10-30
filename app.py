from flask import Flask, make_response
from blueprints.auth.auth import auth_bp
from blueprints.designs.designs import designs_bp
from blueprints.suggestions.suggestions import suggestions_bp
from blueprints.styles.styles import styles_bp
from blueprints.products.products import products_bp
from blueprints.reports.reports import reports_bp

app = Flask(__name__)

app.register_blueprint(auth_bp)
app.register_blueprint(designs_bp)
app.register_blueprint(suggestions_bp)
app.register_blueprint(styles_bp)
app.register_blueprint(products_bp)
app.register_blueprint(reports_bp)


@app.route("/", methods=["GET"])
def index():
    return make_response("<h1>Interior Design API</h1>", 200)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
