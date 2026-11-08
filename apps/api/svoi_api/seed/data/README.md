# Seed data

`cities.csv` is derived from [GeoNames](https://www.geonames.org) (`UA.zip` and
`alternatenames/UA.zip`, retrieved 2026-11-08), licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Changes: populated places with at
least 5000 inhabitants; oblast names and a few town names fixed by hand
(`seed/geonames.py`). Rebuild with `python -m svoi_api.seed.geonames <UA.txt> <alternatenames UA.txt>`.

Everything else in this folder is written for Svoi.
