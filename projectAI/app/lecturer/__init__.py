from flask import Blueprint

lecturer_bp = Blueprint('lecturer', __name__, url_prefix='/lecturer')

from . import routes
