from flask import Blueprint

technician_bp = Blueprint('technician', __name__, url_prefix='/technician')

from . import routes
