import random

left = [
    "admiring",
    "adoring",
    "affectionate",
    "agitated",
    "amazing",
    "angry",
    "awesome",
    "blissful",
    "boring",
    "brave",
    "clever",
    "cocky",
    "compassionate",
    "competent",
    "condescending",
    "confident",
    "cranky",
    "dazzling",
    "determined",
    "distracted",
    "dreamy",
    "eager",
    "ecstatic",
    "elastic",
    "elated",
    "elegant",
    "eloquent",
    "epic",
    "fervent",
    "festive",
    "flamboyant",
    "focused",
    "friendly",
    "frosty",
    "gallant",
    "gifted",
    "goofy",
    "gracious",
    "happy",
    "hardcore",
    "heuristic",
    "hopeful",
    "hungry",
    "infallible",
    "inspiring",
    "jolly",
    "jovial",
    "keen",
    "kind",
    "laughing",
    "loving",
    "lucid",
    "mystifying",
    "modest",
    "musing",
    "naughty",
    "nervous",
    "nifty",
    "nostalgic",
    "objective",
    "optimistic",
    "peaceful",
    "pedantic",
    "pensive",
    "practical",
    "priceless",
    "quirky",
    "quizzical",
    "relaxed",
    "reverent",
    "romantic",
    "sad",
    "serene",
    "sharp",
    "silly",
    "sleepy",
    "stoic",
    "stupefied",
    "suspicious",
    "tender",
    "thirsty",
    "trusting",
    "unruffled",
    "upbeat",
    "vibrant",
    "vigilant",
    "vigorous",
    "wizardly",
    "wonderful",
    "xenodochial",
    "youthful",
    "zealous",
    "zen",
]

right = [
    "albattani",
    "allen",
    "almeida",
    "archimedes",
    "ardinghelli",
    "aryabhata",
    "austin",
    "babbage",
    "banach",
    "bardeen",
    "bartik",
    "bell",
    "bhabha",
    "bhaskara",
    "blackwell",
    "bohr",
    "booth",
    "borg",
    "bose",
    "boyd",
    "brahmagupta",
    "brattain",
    "brown",
    "carson",
    "chandrasekhar",
    "colden",
    "cori",
    "cray",
    "curie",
    "darwin",
    "davinci",
    "dijkstra",
    "dubinsky",
    "easley",
    "einstein",
    "elion",
    "engelbart",
    "euclid",
    "euler",
    "fermat",
    "fermi",
    "feynman",
    "franklin",
    "galileo",
    "gates",
    "goldberg",
    "goldstine",
    "goodall",
    "hamilton",
    "hawking",
    "heisenberg",
    "hodgkin",
    "hoover",
    "hopper",
    "hugle",
    "hypatia",
    "jang",
    "jennings",
    "jepsen",
    "joliot",
    "jones",
    "kalam",
    "kare",
    "keller",
    "khorana",
    "kilby",
    "kirch",
    "knuth",
    "kowalevski",
    "lalande",
    "lamarr",
    "leakey",
    "leavitt",
    "lichterman",
    "liskov",
    "lovelace",
    "lumiere",
    "mahavira",
    "mayer",
    "mccarthy",
    "mcclintock",
    "mclean",
    "mcnulty",
    "meitner",
    "meninsky",
    "mestorf",
    "mirzakhani",
    "morse",
    "newton",
    "nobel",
    "noether",
    "northcutt",
    "noyce",
    "panini",
    "pare",
    "pasteur",
    "payne",
    "perlman",
    "pike",
    "poincare",
    "poitras",
    "ptolemy",
    "raman",
    "ramanujan",
    "ride",
    "ritchie",
    "roentgen",
    "rosalind",
    "saha",
    "sammet",
    "shaw",
    "shockley",
    "sinoussi",
    "snyder",
    "spence",
    "stallman",
    "swanson",
    "swartz",
    "swirles",
    "tesla",
    "thompson",
    "torvalds",
    "turing",
    "varahamihira",
    "visvesvaraya",
    "wescoff",
    "williams",
    "wilson",
    "wing",
    "wozniak",
    "wright",
    "yalow",
    "yonath",
]


def get_random_name(separator="-"):
    """
    Gets a random name
    """
    return '{}{}{}'.format(random.choice(left), separator, random.choice(right))