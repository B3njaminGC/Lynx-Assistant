"""Preparación común: el código vive en la raíz del repo y los datos de cada prueba en una carpeta temporal."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
