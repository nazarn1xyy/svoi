"""Catalog seed data: categories, interests, goals, prompts, clarifications, institutions.

Ids are fixed: production rows reference them, so never renumber; append new rows instead.
"""

import csv
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from svoi_contracts.enums import GoalCode, InstitutionType

CITIES_CSV = Path(__file__).parent / "data" / "cities.csv"


@dataclass(frozen=True)
class Category:
    id: int
    code: str
    emoji: str
    title_uk: str
    title_ru: str
    title_en: str
    position: int
    hidden: bool = False  # "other" holds custom tags and is not listed in the catalog


@dataclass(frozen=True)
class Interest:
    id: int
    category_code: str
    code: str
    title_uk: str
    title_ru: str
    title_en: str


@dataclass(frozen=True)
class Goal:
    code: GoalCode
    emoji: str
    title_uk: str
    title_ru: str
    title_en: str


@dataclass(frozen=True)
class Prompt:
    id: int
    code: str
    title_uk: str
    title_ru: str
    title_en: str


@dataclass(frozen=True)
class Option:
    key: str
    title_uk: str
    title_ru: str
    title_en: str


@dataclass(frozen=True)
class Clarification:
    id: int
    interest_code: str
    question_key: str  # the bot translates clarify.<question_key>
    priority: int
    options: tuple[Option, ...]


@dataclass(frozen=True)
class Institution:
    id: int
    city_geonames_id: int
    name: str
    short_name: str | None
    type: InstitutionType
    source_id: str | None  # EDEBO registry code when known


@dataclass(frozen=True)
class City:
    geonames_id: int
    name_uk: str
    name_ru: str
    name_en: str
    region_uk: str
    region_ru: str
    region_en: str
    country_code: str
    lat: float
    lon: float
    population: int


CATEGORIES: tuple[Category, ...] = (
    Category(1, "sport", "⚽", "Спорт", "Спорт", "Sports", 1),
    Category(2, "games", "🎮", "Ігри", "Игры", "Games", 2),
    Category(3, "music", "🎵", "Музика", "Музыка", "Music", 3),
    Category(4, "movies", "🎬", "Кіно і серіали", "Кино и сериалы", "Movies and TV", 4),
    Category(5, "books", "📚", "Книги", "Книги", "Books", 5),
    Category(6, "creative", "🎨", "Творчість", "Творчество", "Creativity", 6),
    Category(7, "tech", "💻", "Технології", "Технологии", "Tech", 7),
    Category(8, "study", "🎓", "Навчання", "Учёба", "Learning", 8),
    Category(9, "outdoor", "🏕", "Природа і подорожі", "Природа и путешествия", "Outdoors", 9),
    Category(10, "food", "🍕", "Їжа", "Еда", "Food", 10),
    Category(11, "leisure", "🎉", "Дозвілля", "Досуг", "Leisure", 11),
    Category(12, "animals", "🐾", "Тварини", "Животные", "Animals", 12),
    Category(13, "other", "✨", "Інше", "Другое", "Other", 99, hidden=True),
)

_INTERESTS: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "sport": (
        ("football", "Футбол", "Футбол", "Football"),
        ("basketball", "Баскетбол", "Баскетбол", "Basketball"),
        ("volleyball", "Волейбол", "Волейбол", "Volleyball"),
        ("gym", "Тренажерний зал", "Тренажёрный зал", "Gym"),
        ("running", "Біг", "Бег", "Running"),
        ("cycling", "Велосипед", "Велосипед", "Cycling"),
        ("swimming", "Плавання", "Плавание", "Swimming"),
        ("boxing", "Бокс", "Бокс", "Boxing"),
        ("yoga", "Йога", "Йога", "Yoga"),
        ("skateboarding", "Скейтбординг", "Скейтбординг", "Skateboarding"),
        ("table_tennis", "Настільний теніс", "Настольный теннис", "Table tennis"),
        ("martial_arts", "Єдиноборства", "Единоборства", "Martial arts"),
        ("tennis", "Теніс", "Теннис", "Tennis"),
    ),
    "games": (
        ("cs2", "CS2", "CS2", "CS2"),
        ("dota2", "Dota 2", "Dota 2", "Dota 2"),
        ("valorant", "Valorant", "Valorant", "Valorant"),
        ("minecraft", "Minecraft", "Minecraft", "Minecraft"),
        ("fortnite", "Fortnite", "Fortnite", "Fortnite"),
        ("gta", "GTA", "GTA", "GTA"),
        ("lol", "League of Legends", "League of Legends", "League of Legends"),
        ("pubg", "PUBG", "PUBG", "PUBG"),
        ("mobile_games", "Мобільні ігри", "Мобильные игры", "Mobile games"),
        ("board_games", "Настільні ігри", "Настольные игры", "Board games"),
        ("chess", "Шахи", "Шахматы", "Chess"),
    ),
    "music": (
        ("guitar", "Гітара", "Гитара", "Guitar"),
        ("piano", "Фортепіано", "Фортепиано", "Piano"),
        ("singing", "Спів", "Пение", "Singing"),
        ("rap", "Реп", "Рэп", "Rap"),
        ("rock", "Рок", "Рок", "Rock"),
        ("electronic", "Електронна музика", "Электронная музыка", "Electronic music"),
        ("ukrainian_music", "Українська музика", "Украинская музыка", "Ukrainian music"),
        ("concerts", "Концерти", "Концерты", "Concerts"),
        ("djing", "Діджеїнг", "Диджеинг", "DJing"),
        ("kpop", "K-pop", "K-pop", "K-pop"),
        ("festivals", "Фестивалі", "Фестивали", "Festivals"),
    ),
    "movies": (
        ("anime", "Аніме", "Аниме", "Anime"),
        ("marvel", "Marvel", "Marvel", "Marvel"),
        ("horror", "Жахи", "Ужасы", "Horror"),
        ("comedies", "Комедії", "Комедии", "Comedies"),
        ("series", "Серіали", "Сериалы", "TV series"),
        ("documentaries", "Документальне кіно", "Документальное кино", "Documentaries"),
        ("cartoons", "Мультфільми", "Мультфильмы", "Cartoons"),
        ("sci_fi", "Фантастика", "Фантастика", "Sci-fi"),
        ("cinema", "Похід у кіно", "Поход в кино", "Going to the cinema"),
        ("k_dramas", "Дорами", "Дорамы", "K-dramas"),
    ),
    "books": (
        ("fantasy", "Фентезі", "Фэнтези", "Fantasy"),
        ("manga", "Манга", "Манга", "Manga"),
        ("comics", "Комікси", "Комиксы", "Comics"),
        ("classics", "Класика", "Классика", "Classics"),
        ("psychology", "Психологія", "Психология", "Psychology"),
        ("detective", "Детективи", "Детективы", "Detective stories"),
        ("poetry", "Поезія", "Поэзия", "Poetry"),
        ("self_development", "Саморозвиток", "Саморазвитие", "Self-development"),
        ("history", "Історія", "История", "History"),
    ),
    "creative": (
        ("drawing", "Малювання", "Рисование", "Drawing"),
        ("photography", "Фотографія", "Фотография", "Photography"),
        ("video_editing", "Монтаж відео", "Монтаж видео", "Video editing"),
        ("design", "Дизайн", "Дизайн", "Design"),
        ("dancing", "Танці", "Танцы", "Dancing"),
        ("theatre", "Театр", "Театр", "Theatre"),
        ("handmade", "Хендмейд", "Хендмейд", "Handmade"),
        ("writing", "Пишу тексти", "Пишу тексты", "Writing"),
        ("blogging", "Блогінг", "Блогинг", "Blogging"),
        ("cosplay", "Косплей", "Косплей", "Cosplay"),
    ),
    "tech": (
        ("programming", "Програмування", "Программирование", "Programming"),
        ("web_dev", "Веброзробка", "Веб-разработка", "Web development"),
        ("gamedev", "Геймдев", "Геймдев", "Game development"),
        ("ai", "Штучний інтелект", "Искусственный интеллект", "AI"),
        ("robotics", "Робототехніка", "Робототехника", "Robotics"),
        ("pc_building", "Збирання ПК", "Сборка ПК", "PC building"),
        ("crypto", "Криптовалюти", "Криптовалюты", "Crypto"),
        ("gadgets", "Гаджети", "Гаджеты", "Gadgets"),
        ("modeling_3d", "3D-моделювання", "3D-моделирование", "3D modeling"),
        ("cybersecurity", "Кібербезпека", "Кибербезопасность", "Cybersecurity"),
    ),
    "study": (
        ("english", "Англійська мова", "Английский язык", "English"),
        ("languages", "Іноземні мови", "Иностранные языки", "Foreign languages"),
        ("math", "Математика", "Математика", "Math"),
        ("physics", "Фізика", "Физика", "Physics"),
        ("biology", "Біологія", "Биология", "Biology"),
        ("chemistry", "Хімія", "Химия", "Chemistry"),
        ("nmt_prep", "Підготовка до НМТ", "Подготовка к НМТ", "NMT exam prep"),
        ("olympiads", "Олімпіади", "Олимпиады", "Olympiads"),
        ("economics", "Економіка", "Экономика", "Economics"),
        ("debates", "Дебати", "Дебаты", "Debates"),
    ),
    "outdoor": (
        ("hiking", "Походи", "Походы", "Hiking"),
        ("camping", "Кемпінг", "Кемпинг", "Camping"),
        ("fishing", "Риболовля", "Рыбалка", "Fishing"),
        ("travel", "Подорожі", "Путешествия", "Travel"),
        ("city_walks", "Прогулянки містом", "Прогулки по городу", "City walks"),
        ("mountains", "Гори", "Горы", "Mountains"),
        ("road_trips", "Автоподорожі", "Автопутешествия", "Road trips"),
        ("gardening", "Садівництво", "Садоводство", "Gardening"),
        ("beach", "Пляжний відпочинок", "Пляжный отдых", "Beach holidays"),
    ),
    "food": (
        ("cooking", "Кулінарія", "Кулинария", "Cooking"),
        ("baking", "Випічка", "Выпечка", "Baking"),
        ("coffee", "Кава", "Кофе", "Coffee"),
        ("sushi", "Суші", "Суши", "Sushi"),
        ("pizza", "Піца", "Пицца", "Pizza"),
        ("street_food", "Стрітфуд", "Стритфуд", "Street food"),
        ("vegetarian", "Вегетаріанство", "Вегетарианство", "Vegetarian food"),
        ("tea", "Чай", "Чай", "Tea"),
        ("bbq", "Шашлики", "Шашлыки", "BBQ"),
    ),
    "leisure": (
        ("parties", "Вечірки", "Вечеринки", "Parties"),
        ("quests", "Квести", "Квесты", "Escape rooms"),
        ("karaoke", "Караоке", "Караоке", "Karaoke"),
        ("bowling", "Боулінг", "Боулинг", "Bowling"),
        ("volunteering", "Волонтерство", "Волонтёрство", "Volunteering"),
        ("memes", "Меми", "Мемы", "Memes"),
        ("astrology", "Астрологія", "Астрология", "Astrology"),
        ("podcasts", "Подкасти", "Подкасты", "Podcasts"),
        ("mafia", "Мафія", "Мафия", "Mafia party game"),
        ("standup", "Стендап", "Стендап", "Stand-up comedy"),
    ),
    "animals": (
        ("dogs", "Собаки", "Собаки", "Dogs"),
        ("cats", "Коти", "Кошки", "Cats"),
        ("horses", "Коні", "Лошади", "Horses"),
        ("aquarium", "Акваріумістика", "Аквариумистика", "Aquarium fish"),
        ("reptiles", "Рептилії", "Рептилии", "Reptiles"),
        ("birds", "Птахи", "Птицы", "Birds"),
        ("animal_rescue", "Допомога тваринам", "Помощь животным", "Animal rescue"),
        ("pet_training", "Дресирування", "Дрессировка", "Pet training"),
    ),
}

# ids follow category order, then the order inside a category; append only
INTERESTS: tuple[Interest, ...] = tuple(
    Interest(index, category, *row)
    for index, (category, row) in enumerate(
        ((c, row) for c, rows in _INTERESTS.items() for row in rows), start=1
    )
)

GOALS: tuple[Goal, ...] = (
    Goal(GoalCode.friends, "👫", "Знайти друзів", "Найти друзей", "Find friends"),
    Goal(GoalCode.walks, "🚶", "Компанія для прогулянок", "Компания для прогулок", "Walk buddies"),
    Goal(GoalCode.sport, "⚽", "Напарник для спорту", "Напарник для спорта", "Sports partner"),
    Goal(GoalCode.study, "📚", "Разом навчатися", "Учиться вместе", "Study together"),
    Goal(GoalCode.gaming, "🎮", "Грати онлайн", "Играть онлайн", "Play online"),
    Goal(GoalCode.creative, "🎨", "Творчість, проєкти", "Творчество, проекты", "Creative projects"),
    Goal(GoalCode.chat, "💬", "Просто поспілкуватися", "Просто пообщаться", "Just chat"),
)

PROMPTS: tuple[Prompt, ...] = (
    Prompt(
        1,
        "weekend",
        "🌅 Ідеальні вихідні — це…",
        "🌅 Идеальные выходные — это…",
        "🌅 My perfect weekend is…",
    ),
    Prompt(
        2,
        "looking_for",
        "🔍 Шукаю людину, яка…",
        "🔍 Ищу человека, который…",
        "🔍 Looking for someone who…",
    ),
    Prompt(
        3,
        "teach_learn",
        "🎓 Можу навчити / хочу навчитися…",
        "🎓 Могу научить / хочу научиться…",
        "🎓 I can teach / want to learn…",
    ),
    Prompt(4, "listening", "🎧 Зараз слухаю…", "🎧 Сейчас слушаю…", "🎧 Listening to…"),
)

_PLAYS = Option("plays", "граю", "играю", "I play")
_LISTENS = Option("listens", "слухаю", "слушаю", "I listen")
_LEARNING = Option("learning", "вчуся", "учусь", "learning")
_WATCHES = Option("watches", "дивлюся", "смотрю", "I watch")
_FOR_FUN = Option("for_fun", "для душі", "для души", "for fun")
_RANKED = Option("ranked", "рейтинг", "рейтинг", "ranked")
_TOURNAMENTS = Option("tournaments", "турніри", "турниры", "tournaments")

CLARIFICATIONS: tuple[Clarification, ...] = (
    Clarification(1, "guitar", "guitar_play", 10, (_PLAYS, _LISTENS, _LEARNING)),
    Clarification(2, "piano", "piano_play", 10, (_PLAYS, _LISTENS, _LEARNING)),
    Clarification(3, "football", "football_role", 9, (_PLAYS, _WATCHES)),
    Clarification(4, "basketball", "basketball_role", 8, (_PLAYS, _WATCHES)),
    Clarification(5, "cs2", "cs2_level", 9, (_FOR_FUN, _RANKED, _TOURNAMENTS)),
    Clarification(6, "dota2", "dota2_level", 8, (_FOR_FUN, _RANKED, _TOURNAMENTS)),
    Clarification(
        7,
        "gym",
        "gym_goal",
        7,
        (
            Option("bulking", "набираю масу", "набираю массу", "bulking"),
            Option("fit", "тримаю форму", "держу форму", "keeping fit"),
            Option("beginner", "тільки починаю", "только начинаю", "just starting"),
        ),
    ),
    Clarification(
        8,
        "running",
        "running_distance",
        6,
        (
            Option("short", "до 5 км", "до 5 км", "up to 5 km"),
            Option("long", "10 км і більше", "10 км и больше", "10 km and more"),
        ),
    ),
    Clarification(
        9,
        "drawing",
        "drawing_medium",
        6,
        (
            Option("paper", "на папері", "на бумаге", "on paper"),
            Option("digital", "діджитал", "диджитал", "digital"),
        ),
    ),
    Clarification(
        10,
        "photography",
        "photo_gear",
        5,
        (
            Option("phone", "на телефон", "на телефон", "on a phone"),
            Option("camera", "на камеру", "на камеру", "with a camera"),
        ),
    ),
    Clarification(
        11,
        "programming",
        "programming_level",
        7,
        (
            _LEARNING,
            Option("hobby", "для себе", "для себя", "as a hobby"),
            Option("work", "працюю", "работаю", "professionally"),
        ),
    ),
    Clarification(
        12,
        "english",
        "english_level",
        6,
        (
            Option("basic", "базовий", "базовый", "basic"),
            Option("intermediate", "середній", "средний", "intermediate"),
            Option("fluent", "вільно", "свободно", "fluent"),
        ),
    ),
    Clarification(
        13,
        "anime",
        "anime_format",
        4,
        (
            Option("subs", "з субтитрами", "с субтитрами", "subtitled"),
            Option("dub", "в озвучці", "в озвучке", "dubbed"),
        ),
    ),
    Clarification(
        14,
        "dancing",
        "dance_style",
        5,
        (
            Option("hiphop", "хіп-хоп", "хип-хоп", "hip-hop"),
            Option("contemporary", "контемпорарі", "контемпорари", "contemporary"),
            Option("ballroom", "бальні", "бальные", "ballroom"),
        ),
    ),
    Clarification(
        15,
        "chess",
        "chess_format",
        4,
        (
            Option("online", "онлайн", "онлайн", "online"),
            Option("offline", "наживо", "вживую", "in person"),
        ),
    ),
)

_KYIV, _VINNYTSIA, _MOHYLIV = 703448, 689558, 700918
_UNI, _COLLEGE = InstitutionType.university, InstitutionType.college

INSTITUTIONS: tuple[Institution, ...] = (
    Institution(
        1,
        _MOHYLIV,
        "Могилів-Подільський монтажно-економічний фаховий коледж",
        "МПМЕФК",
        _COLLEGE,
        "666",
    ),
    Institution(
        2,
        _MOHYLIV,
        "Могилів-Подільський технолого-економічний фаховий коледж ВНАУ",
        "МПТЕФК ВНАУ",
        _COLLEGE,
        "667",
    ),
    Institution(
        3, _MOHYLIV, "Могилів-Подільський медичний фаховий коледж", "МПМФК", _COLLEGE, "976"
    ),
    Institution(4, _VINNYTSIA, "Вінницький національний технічний університет", "ВНТУ", _UNI, None),
    Institution(
        5,
        _VINNYTSIA,
        "Вінницький державний педагогічний університет імені Михайла Коцюбинського",
        "ВДПУ",
        _UNI,
        None,
    ),
    Institution(
        6,
        _VINNYTSIA,
        "Вінницький національний медичний університет імені М. І. Пирогова",
        "ВНМУ",
        _UNI,
        None,
    ),
    Institution(7, _VINNYTSIA, "Вінницький національний аграрний університет", "ВНАУ", _UNI, None),
    Institution(
        8,
        _VINNYTSIA,
        "Донецький національний університет імені Василя Стуса",
        "ДонНУ",
        _UNI,
        None,
    ),
    Institution(9, _VINNYTSIA, "Вінницький кооперативний інститут", "ВКІ", _UNI, None),
    Institution(
        10,
        _KYIV,
        "Київський національний університет імені Тараса Шевченка",
        "КНУ",
        _UNI,
        None,
    ),
    Institution(
        11,
        _KYIV,
        "Національний технічний університет України «КПІ імені Ігоря Сікорського»",
        "КПІ",
        _UNI,
        None,
    ),
    Institution(
        12,
        _KYIV,
        "Національний університет «Києво-Могилянська академія»",
        "НаУКМА",
        _UNI,
        None,
    ),
    Institution(
        13,
        _KYIV,
        "Національний медичний університет імені О. О. Богомольця",
        "НМУ",
        _UNI,
        None,
    ),
    Institution(
        14,
        _KYIV,
        "Київський національний економічний університет імені Вадима Гетьмана",
        "КНЕУ",
        _UNI,
        None,
    ),
    Institution(15, _KYIV, "Національний авіаційний університет", "НАУ", _UNI, None),
    Institution(
        16,
        _KYIV,
        "Київський національний університет будівництва і архітектури",
        "КНУБА",
        _UNI,
        None,
    ),
    Institution(
        17,
        _KYIV,
        "Київський столичний університет імені Бориса Грінченка",
        "КСУ",
        _UNI,
        None,
    ),
    Institution(
        18,
        _KYIV,
        "Київський національний лінгвістичний університет",
        "КНЛУ",
        _UNI,
        None,
    ),
    Institution(
        19,
        _KYIV,
        "Національний університет біоресурсів і природокористування України",
        "НУБіП",
        _UNI,
        None,
    ),
)


@cache
def load_cities() -> tuple[City, ...]:
    """Cities from data/cities.csv (GeoNames, CC BY 4.0)."""
    with CITIES_CSV.open(encoding="utf-8", newline="") as f:
        return tuple(
            City(
                geonames_id=int(row["geonames_id"]),
                name_uk=row["name_uk"],
                name_ru=row["name_ru"],
                name_en=row["name_en"],
                region_uk=row["region_uk"],
                region_ru=row["region_ru"],
                region_en=row["region_en"],
                country_code=row["country_code"],
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                population=int(row["population"]),
            )
            for row in csv.DictReader(f)
        )
