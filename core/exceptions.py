"""Excepciones de dominio compartidas por los servicios de todas las apps."""


class ReglaNegocioError(Exception):
    """Se viola una regla de negocio (RN-xxx). El mensaje es apto para mostrar al usuario."""
