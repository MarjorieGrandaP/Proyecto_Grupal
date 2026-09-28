"""Pruebas aisladas: no importan app.py ni conectan a PostgreSQL."""
import unittest
from html.parser import HTMLParser
from pathlib import Path
from flask import Flask, render_template
from werkzeug.datastructures import MultiDict
from forms import UsuarioForm, PerfilForm, ClienteForm, ProveedorForm
from forms.nombre_personal import PATRON_NOMBRE, MENSAJE_NOMBRE

CAMPOS = (
    (UsuarioForm, "nombres"), (UsuarioForm, "apellidos"),
    (PerfilForm, "nombres"), (PerfilForm, "apellidos"),
    (ClienteForm, "nombre"), (ProveedorForm, "contacto"),
)
VALIDOS = ("María José", "José Luis", "Peña", "Muñoz", "María", "María  José", "ÜÑ", "Li")
INVALIDOS = ("Ana-María", "O'Connor", "María_", "000", "María123", "José@", "", "A", "  ", "--", "''", "Ana_", "A"*101)


class Inputs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inputs = {}
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input":
            self.inputs[attrs.get("name")] = attrs


class NombresPersonales(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(Path("templates").resolve()))
        self.app.config.update(SECRET_KEY="test", WTF_CSRF_ENABLED=False)

    def test_backend_seis_campos(self):
        with self.app.test_request_context():
            for cls, name in CAMPOS:
                for value in VALIDOS + INVALIDOS:
                    with self.subTest(form=cls.__name__, field=name, value=value):
                        form = cls(MultiDict({name: value}))
                        self.assertEqual(getattr(form, name).validate(form), value in VALIDOS)

    def test_atributos_frontend_en_plantillas(self):
        from jinja2 import DictLoader, ChoiceLoader
        # Sustituir solo el layout para renderizar el contenido real sin rutas ni BD.
        self.app.jinja_loader = ChoiceLoader([
            DictLoader({"base.html": "{% block content %}{% endblock %}"}),
            self.app.jinja_loader,
        ])
        cases = (
            ("registro.html", UsuarioForm, ("nombres", "apellidos")),
            ("perfil.html", PerfilForm, ("nombres", "apellidos")),
            ("formulario_cliente.html", ClienteForm, ("nombre",)),
            ("formulario_proveedor.html", ProveedorForm, ("contacto",)),
        )
        with self.app.test_request_context():
            self.app.jinja_env.globals["url_for"] = lambda *a, **kw: "#"
            for template, cls, names in cases:
                parser = Inputs()
                parser.feed(render_template(template, form=cls(), perfil={}, current_user={}))
                for name in names:
                    with self.subTest(template=template, field=name):
                        attrs = parser.inputs[name]
                        self.assertEqual(attrs["pattern"], PATRON_NOMBRE)
                        self.assertEqual(attrs["minlength"], "2")
                        self.assertEqual(attrs["data-validation"], "required,minlength:2,maxlength:100")
                        self.assertEqual(attrs["data-validation-message"], MENSAJE_NOMBRE)

    def test_campos_no_personales_conservan_numeros(self):
        with self.app.test_request_context():
            for cls, name, value in (
                (ProveedorForm, "empresa", "Empresa 123"),
                (ProveedorForm, "categoria", "Categoría 123"),
                (ClienteForm, "equipo", "Laptop 123"),
            ):
                form = cls(MultiDict({name: value}))
                field = getattr(form, name)
                self.assertTrue(field.validate(form))
                if name != "equipo":
                    self.assertNotIn("pattern", field.render_kw or {})

if __name__ == "__main__":
    unittest.main()
