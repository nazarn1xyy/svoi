"""Builds seed/data/cities.csv from GeoNames dumps (CC BY 4.0, https://www.geonames.org).

Usage: python -m svoi_api.seed.geonames <UA.txt> <alternatenames/UA.txt>
Download both from https://download.geonames.org/export/dump/ (UA.zip, alternatenames/UA.zip).
"""

import csv
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

CITIES_CSV = Path(__file__).parent / "data" / "cities.csv"
MIN_POPULATION = 5000
CITY_CODES = frozenset({"PPL", "PPLA", "PPLA2", "PPLA3", "PPLA4", "PPLC"})
LANGS = ("uk", "ru", "en")
# alternateNamesV2 columns "from" and "to": a bounded period means a former or future name
_FROM, _TO = 8, 9
FIELDS = (
    "geonames_id",
    "name_uk",
    "name_ru",
    "name_en",
    "region_uk",
    "region_ru",
    "region_en",
    "country_code",
    "lat",
    "lon",
    "population",
)


# GeoNames spells oblasts inconsistently ("Волинська Область", "Чернігівська"); fix by admin1 code.
REGIONS: dict[str, tuple[str, str, str]] = {
    "01": ("Черкаська область", "Черкасская область", "Cherkasy Oblast"),
    "02": ("Чернігівська область", "Черниговская область", "Chernihiv Oblast"),
    "03": ("Чернівецька область", "Черновицкая область", "Chernivtsi Oblast"),
    "04": ("Дніпропетровська область", "Днепропетровская область", "Dnipropetrovsk Oblast"),
    "05": ("Донецька область", "Донецкая область", "Donetsk Oblast"),
    "06": ("Івано-Франківська область", "Ивано-Франковская область", "Ivano-Frankivsk Oblast"),
    "07": ("Харківська область", "Харьковская область", "Kharkiv Oblast"),
    "08": ("Херсонська область", "Херсонская область", "Kherson Oblast"),
    "09": ("Хмельницька область", "Хмельницкая область", "Khmelnytskyi Oblast"),
    "10": ("Кіровоградська область", "Кировоградская область", "Kirovohrad Oblast"),
    "11": (
        "Автономна Республіка Крим",
        "Автономная Республика Крым",
        "Autonomous Republic of Crimea",
    ),
    "12": ("Київ", "Киев", "Kyiv"),
    "13": ("Київська область", "Киевская область", "Kyiv Oblast"),
    "14": ("Луганська область", "Луганская область", "Luhansk Oblast"),
    "15": ("Львівська область", "Львовская область", "Lviv Oblast"),
    "16": ("Миколаївська область", "Николаевская область", "Mykolaiv Oblast"),
    "17": ("Одеська область", "Одесская область", "Odesa Oblast"),
    "18": ("Полтавська область", "Полтавская область", "Poltava Oblast"),
    "19": ("Рівненська область", "Ровенская область", "Rivne Oblast"),
    "20": ("Севастополь", "Севастополь", "Sevastopol"),
    "21": ("Сумська область", "Сумская область", "Sumy Oblast"),
    "22": ("Тернопільська область", "Тернопольская область", "Ternopil Oblast"),
    "23": ("Вінницька область", "Винницкая область", "Vinnytsia Oblast"),
    "24": ("Волинська область", "Волынская область", "Volyn Oblast"),
    "25": ("Закарпатська область", "Закарпатская область", "Zakarpattia Oblast"),
    "26": ("Запорізька область", "Запорожская область", "Zaporizhzhia Oblast"),
    "27": ("Житомирська область", "Житомирская область", "Zhytomyr Oblast"),
}

# Towns GeoNames has no Ukrainian name for; other Latin-only entries (suburbs) are skipped.
NAME_OVERRIDES: dict[int, tuple[str, str]] = {
    618835: ("Жидачів", "Жидачов"),
    686868: ("Золоте", "Золотое"),
    687237: ("Жданівка", "Ждановка"),
    687392: ("Зеленодольськ", "Зеленодольск"),
    689428: ("Володимирець", "Владимирец"),
    690771: ("Українськ", "Украинск"),
    692105: ("Довжанськ", "Довжанск"),
    692254: ("Суходільськ", "Суходольск"),
    692953: ("Станиця Луганська", "Станица Луганская"),
    692975: ("Кадіївка", "Кадиевка"),
    694403: ("Сіверськ", "Северск"),
    694677: ("Селидове", "Селидово"),
    694725: ("Щастя", "Счастье"),
    695357: ("Курахове", "Курахово"),
    695581: ("Родинське", "Родинское"),
    695789: ("Ратне", "Ратно"),
    695935: ("Радехів", "Радехов"),
    696566: ("Попасна", "Попасная"),
    698597: ("Олевськ", "Олевск"),
    699557: ("Новогродівка", "Новогродовка"),
    699675: ("Новоазовськ", "Новоазовск"),
    700568: ("Миколаїв", "Николаев"),
    701845: ("Мар’їнка", "Марьинка"),
    701906: ("Маневичі", "Маневичи"),
    702417: ("Люботин", "Люботин"),
    702563: ("Лутугине", "Лутугино"),
    704393: ("Красногорівка", "Красногоровка"),
    705809: ("Голубівка", "Голубовка"),  # renamed from Kirovsk in 2016
    704422: ("Покровськ", "Покровск"),
    706352: ("Ходорів", "Ходоров"),
    706466: ("Харцизьк", "Харцызск"),
    707027: ("Кам’янка-Бузька", "Каменка-Бугская"),
    707292: ("Ізюм", "Изюм"),
    710915: ("Часів Яр", "Часов Яр"),
    713259: ("Антрацит", "Антрацит"),
}


def _is_cyrillic(text: str) -> bool:
    return any("\u0400" <= ch <= "\u04ff" for ch in text)


@dataclass(frozen=True)
class _Place:
    geonames_id: int
    name: str
    lat: str
    lon: str
    feature_code: str
    admin1: str
    population: int


def _read_places(path: Path) -> list[_Place]:
    cities: list[_Place] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            place = _Place(int(row[0]), row[1], row[4], row[5], row[7], row[10], int(row[14] or 0))
            if (
                row[6] == "P"
                and place.feature_code in CITY_CODES
                and place.population >= MIN_POPULATION
            ):
                cities.append(place)
    return cities


def _read_names(path: Path, wanted: set[int]) -> dict[int, dict[str, str]]:
    # rank: preferred and short names first; historic and colloquial ones never
    best: dict[int, dict[str, tuple[int, str]]] = defaultdict(dict)
    with path.open(encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            geonames_id, lang, name = int(row[1]), row[2], row[3]
            if geonames_id not in wanted or lang not in LANGS:
                continue
            preferred, short, colloquial, historic = (row[i] == "1" for i in range(4, 8))
            if colloquial or historic or any(row[_FROM : _TO + 1]):
                continue
            rank = 0 if preferred else 1 if short else 2
            if lang != "en" and not _is_cyrillic(name):
                rank += 10  # GeoNames files some Latin spellings under uk/ru
            current = best[geonames_id].get(lang)
            if current is None or rank < current[0]:
                best[geonames_id][lang] = (rank, name)
    return {gid: {lang: name for lang, (_, name) in names.items()} for gid, names in best.items()}


def build(places_path: Path, names_path: Path) -> list[dict[str, str]]:
    """Rows for cities.csv, sorted by geonames_id for deterministic output."""
    cities = _read_places(places_path)
    names = _read_names(names_path, {c.geonames_id for c in cities})
    rows = []
    for city in sorted(cities, key=lambda c: c.geonames_id):
        own = names.get(city.geonames_id, {})
        uk, ru = NAME_OVERRIDES.get(city.geonames_id, (own.get("uk", ""), own.get("ru", "")))
        if not _is_cyrillic(uk) or city.admin1 not in REGIONS:
            continue
        rows.append(
            {
                "geonames_id": str(city.geonames_id),
                "name_uk": uk,
                "name_ru": ru if _is_cyrillic(ru) else uk,
                "name_en": own.get("en", city.name),
                **dict(
                    zip(("region_uk", "region_ru", "region_en"), REGIONS[city.admin1], strict=True)
                ),
                "country_code": "UA",
                "lat": city.lat,
                "lon": city.lon,
                "population": str(city.population),
            }
        )
    return rows


def main(argv: list[str]) -> None:
    """Rewrite cities.csv from the two dump files."""
    rows = build(Path(argv[0]), Path(argv[1]))
    with CITIES_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main(sys.argv[1:])
