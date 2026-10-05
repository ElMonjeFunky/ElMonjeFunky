- 👋 Hi, I’m @ElMonjeFunky is the 1
- 👀 I’m interested in 2
- 🌱 I’m currently learning 3
- 💞️ I’m looking to collaborate on 4
- 📫 How to reach me ? 5
- 😄 Pronouns are: 666
- ⚡ Fun fact: 7

<!---
ElMonjeFunky/ElMonjeFunky is a ✨ special ✨ repository because its `README.md` (this file) appears on your GitHub profile.
You can click the Preview link to take a look at your changes.
--->

## Informe semanal de melón

- `semanas_2026_ia.json`: tabla fecha → semana (S01–S53, ISO, lunes a domingo) con instrucciones para etiquetar con IA.
- `informe_semanal.py`: lee los datos brutos (.xlsx o .csv), añade la semana a cada entrada y resume por semana y variedad el azúcar (°Brix) y la firmeza (media, mínimo y máximo).

```
pip install -r requirements.txt
python3 informe_semanal.py datos_brutos.xlsx
```

Detecta solas las columnas de fecha, variedad, azúcar/brix y firmeza; si se llaman distinto, indícalas con `--fecha`, `--variedad`, `--azucar`, `--firmeza`.

## Volcado de escandallo (ERP)

`escandallo.py` interpreta el CSV `VOLCADO_GLOBAL_ESCANDALLO_2026_MELON_.csv` (un bloque por producto + variedad + finca) y genera `informe_escandallo_melon_2026.xlsx`:

- **Variedad x Finca**: azúcar (media/mín/máx a partir de la distribución por °Brix) y firmeza (media/mín/máx) de cada variedad en cada finca.
- **Firmeza semanal**: firmeza por variedad, finca y semana (el azúcar viene sin fecha en el volcado).
- **Datos firmeza / Datos azúcar**: datos extraídos, una fila por medida.
- **Revisar**: medidas fuera de escala.

Los nombres de variedad se rellenan en `variedades.csv` (`codigo,nombre`); después se vuelve a ejecutar:

```
python3 escandallo.py VOLCADO_GLOBAL_ESCANDALLO_2026_MELON_.csv
```
