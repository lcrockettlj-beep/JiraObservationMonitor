from pathlib import Path

from flask import Flask, render_template

from ui.ui_mapper import build_homepage_view_model


BASE_DIR = Path(__file__).resolve().parent

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)


@app.route("/")
def home():
    homepage_vm = build_homepage_view_model(base_dir=BASE_DIR)
    return render_template("home.html", home=homepage_vm.to_dict())


@app.route("/site/<site_key>")
def site_detail(site_key: str):
    homepage_vm = build_homepage_view_model(base_dir=BASE_DIR)

    all_sites = (
        homepage_vm.critical_sites
        + homepage_vm.warning_sites
        + homepage_vm.stable_sites
    )

    site = next((item for item in all_sites if item.site_key == site_key), None)

    return render_template(
        "site.html",
        home=homepage_vm.to_dict(),
        site=site.to_dict() if site else None,
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)