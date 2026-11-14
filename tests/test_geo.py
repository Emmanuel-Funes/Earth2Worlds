import pytest

from rotaterra.geo import poligono_desde_esquinas, validar_dentro_argentina


def test_esquinas_de_google_maps():
    p = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295")
    assert p["coordinates"][0] == [[-65.3, -33.7], [-65.295, -33.7], [-65.295, -33.705], [-65.3, -33.7]]


def test_tolera_punto_y_coma_de_mas():
    assert poligono_desde_esquinas("-33.7, -65.3; -33.7, -65.29; -33.71, -65.29;") == \
        poligono_desde_esquinas("-33.7, -65.3; -33.7, -65.29; -33.71, -65.29")


def test_errores_claros():
    with pytest.raises(ValueError, match="al menos 3"):
        poligono_desde_esquinas("-33.7, -65.3; -33.7, -65.29")
    with pytest.raises(ValueError, match="mal escrita"):
        poligono_desde_esquinas("-33.7 -65.3; -33.7, -65.29; -33.71, -65.29")


def test_validar_dentro_argentina():
    # Lote en San Luis (adentro)
    p_ok = poligono_desde_esquinas("-33.700, -65.300; -33.700, -65.295; -33.705, -65.295")
    validar_dentro_argentina(p_ok)

    # Lote fuera de Argentina (Madrid, España)
    p_fuera = poligono_desde_esquinas("40.41, -3.70; 40.42, -3.70; 40.42, -3.69")
    with pytest.raises(ValueError, match="dentro del territorio de la República Argentina"):
        validar_dentro_argentina(p_fuera)
