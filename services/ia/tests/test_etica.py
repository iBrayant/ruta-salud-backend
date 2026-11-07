from app.domain.etica import detectar, ocultar_datos_personales


def test_detecta_lenguaje_estigmatizante():
    assert detectar("La comunidad es pobre y peligrosa")
    assert detectar("Es una zona roja del municipio")
    assert detectar("Hay que atender primero a los vulnerables")


def test_no_marca_lenguaje_respetuoso():
    texto = ("La vereda tiene una alta necesidad de atención por la baja cobertura de acueducto "
             "y el mayor tiempo de viaje al servicio de salud.")
    assert detectar(texto) == []


def test_detecta_contenido_clinico_en_chat():
    assert detectar("Le recomiendo esta dosis de acetaminofén", incluir_clinico=True)


def test_detecta_afirmaciones_imprecisas_sobre_accesibilidad():
    assert detectar("El Carmen tiene accesibilidad nula", incluir_imprecision=True)
    assert detectar("La vereda no tiene acceso", incluir_imprecision=True)
    assert not detectar("El Carmen es la más lejana del conjunto (accesibilidad relativa 0)", incluir_imprecision=True)


def test_contexto_incluye_lluvia_por_hora_durante_visita():
    from app.domain.contexto import hechos_ruta
    parada = {"posicion": 1, "vereda_id": "05-18", "nombre": "El Carmen", "corregimiento": "Sur Oriental",
              "llegada": "09:10", "salida": "09:55", "tramo_km": 18.0, "tramo_min": 44.0,
              "puntaje": {"prioridad": 0.64, "vulnerabilidad": 0.70, "accesibilidad": 0.0, "equidad": 1.0,
                          "dias_sin_visita": None, "lluvia_fuerte": True}}
    clima = {"05-18": {"prob_lluvia_max": 70, "precipitacion_mm": 3.0,
                       "por_hora": {"08": {"prob": 20, "mm": 0.0}, "09": {"prob": 45, "mm": 0.2},
                                    "14": {"prob": 70, "mm": 2.0}}}}
    h = hechos_ruta({"paradas": [parada], "clima_por_vereda": clima})
    ll = h["paradas"][0]["lluvia"]
    assert ll["durante_visita"]["prob_max_pct"] == 45      # 09:10–09:55 → solo la hora 09
    assert ll["por_hora"]["14:00"] == "70% / 2.0 mm"
    assert "accesibilidad" in h["glosario"]


def test_oculta_datos_personales():
    t, n = ocultar_datos_personales("Llamar a 3101234567 o a la cédula 1069123456, correo a@b.co")
    assert "3101234567" not in t and "1069123456" not in t and "a@b.co" not in t
    assert n == 3
