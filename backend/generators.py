"""
Generators for short Twitch usernames:
- 3-character (all letters, letters+digits)
- 4-character (all letters, letters+digits, aesthetic patterns)
- Curated English dictionary words (3, 4, 5 characters)
- Pronounceable phonetic names (CVC, CVCV, VCV)
- Custom pattern generator (e.g. 'z***', 'vk**', '*gg')
- Custom wordlist file reader
"""

import string
import itertools
from pathlib import Path
from typing import Generator, List, Set
from .config import DATA_DIR, MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH, RESERVED_USERNAMES

LETTERS = string.ascii_lowercase
DIGITS = string.digits
ALPHANUMERIC = LETTERS + DIGITS
CONSONANTS = "bcdfghjklmnpqrstvwxyz"
VOWELS = "aeiou"

def is_valid_syntax(username: str) -> bool:
    """Check if a username adheres to Twitch's syntactic rules."""
    u = username.lower().strip()
    if len(u) < MIN_USERNAME_LENGTH or len(u) > MAX_USERNAME_LENGTH:
        return False
    if u.startswith("_"):
        return False
    if not all(c in ALPHANUMERIC or c == '_' for c in u):
        return False
    if u in RESERVED_USERNAMES:
        return False
    return True

def generate_3char_letters() -> Generator[str, None, None]:
    """Generate all 17,576 3-letter combinations ('aaa' -> 'zzz')."""
    for c1, c2, c3 in itertools.product(LETTERS, repeat=3):
        yield f"{c1}{c2}{c3}"

def generate_3char_alphanumeric() -> Generator[str, None, None]:
    """Generate all 46,656 3-alphanumeric combinations."""
    for c1, c2, c3 in itertools.product(ALPHANUMERIC, repeat=3):
        yield f"{c1}{c2}{c3}"

def generate_4char_letters() -> Generator[str, None, None]:
    """Generate all 456,976 4-letter combinations ('aaaa' -> 'zzzz')."""
    for p in itertools.product(LETTERS, repeat=4):
        yield "".join(p)

def generate_4char_alphanumeric() -> Generator[str, None, None]:
    """Generate all 1,679,616 4-alphanumeric combinations."""
    for p in itertools.product(ALPHANUMERIC, repeat=4):
        yield "".join(p)

def load_dictionary_words(length: int) -> List[str]:
    """Load curated dictionary words of specified length (3, 4, 5)."""
    filename = DATA_DIR / f"words_{length}char.txt"
    if not filename.exists():
        return []
    with open(filename, "r", encoding="utf-8") as f:
        words = [line.strip().lower() for line in f if line.strip()]
    return [w for w in words if is_valid_syntax(w)]

def generate_pronounceable(length: int = 4) -> Generator[str, None, None]:
    """
    Generate clean, pronounceable phonetic names.
    length=3: CVC (Consonant - Vowel - Consonant, e.g. 'bax', 'zet', 'lyn')
    length=4: CVCV (Consonant - Vowel - Consonant - Vowel, e.g. 'kuro', 'zemo', 'taki')
              or VCV+C (e.g. 'axon', 'odin')
    """
    if length == 3:
        for c1 in CONSONANTS:
            for v in VOWELS:
                for c2 in CONSONANTS:
                    yield f"{c1}{v}{c2}"
    elif length == 4:
        for c1 in CONSONANTS:
            for v1 in VOWELS:
                for c2 in CONSONANTS:
                    for v2 in VOWELS:
                        yield f"{c1}{v1}{c2}{v2}"
        # Also V-C-V-C pattern
        for v1 in VOWELS:
            for c1 in CONSONANTS:
                for v2 in VOWELS:
                    for c2 in CONSONANTS:
                        yield f"{v1}{c1}{v2}{c2}"
    elif length == 5:
        # C-V-C-V-C pattern (e.g. kurox, valek, zenon)
        for c1 in CONSONANTS:
            for v1 in VOWELS:
                for c2 in CONSONANTS:
                    for v2 in VOWELS:
                        for c3 in CONSONANTS:
                            yield f"{c1}{v1}{c2}{v2}{c3}"
        # V-C-V-C-V (e.g. akira, otaku)
        for v1 in VOWELS:
            for c1 in CONSONANTS:
                for v2 in VOWELS:
                    for c2 in CONSONANTS:
                        for v3 in VOWELS:
                            yield f"{v1}{c1}{v2}{c2}{v3}"

def generate_aesthetic_patterns(length: int = 4) -> Generator[str, None, None]:
    """
    Generate rare/aesthetic OG patterns:
    length=4: aaaa, aabb, abab, abba, x_x_
    length=5: aaaaa, aaabb, aabbb, ababa, abcba (palindromes)
    """
    seen: Set[str] = set()

    if length == 5:
        # Repetition 5 of same char (e.g. 77777, xxxxx, zzzzz)
        for c in ALPHANUMERIC:
            word = c * 5
            if word not in seen and is_valid_syntax(word):
                seen.add(word)
                yield word
        # AAABB / AABBB
        for c1 in ALPHANUMERIC:
            for c2 in ALPHANUMERIC:
                if c1 != c2:
                    for w in (f"{c1}{c1}{c1}{c2}{c2}", f"{c1}{c1}{c2}{c2}{c2}"):
                        if w not in seen and is_valid_syntax(w):
                            seen.add(w)
                            yield w
        # ABABA
        for c1 in ALPHANUMERIC:
            for c2 in ALPHANUMERIC:
                if c1 != c2:
                    w = f"{c1}{c2}{c1}{c2}{c1}"
                    if w not in seen and is_valid_syntax(w):
                        seen.add(w)
                        yield w
        # ABCBA (Palindromes)
        for c1 in LETTERS:
            for c2 in LETTERS:
                for c3 in LETTERS:
                    if len({c1, c2, c3}) >= 2:
                        w = f"{c1}{c2}{c3}{c2}{c1}"
                        if w not in seen and is_valid_syntax(w):
                            seen.add(w)
                            yield w
        return

    # Repetition 4 of same char
    for c in ALPHANUMERIC:
        word = c * 4
        if word not in seen and is_valid_syntax(word):
            seen.add(word)
            yield word

    # AABB
    for c1 in ALPHANUMERIC:
        for c2 in ALPHANUMERIC:
            if c1 != c2:
                word = f"{c1}{c1}{c2}{c2}"
                if word not in seen and is_valid_syntax(word):
                    seen.add(word)
                    yield word

    # ABAB
    for c1 in ALPHANUMERIC:
        for c2 in ALPHANUMERIC:
            if c1 != c2:
                word = f"{c1}{c2}{c1}{c2}"
                if word not in seen and is_valid_syntax(word):
                    seen.add(word)
                    yield word

    # ABBA
    for c1 in ALPHANUMERIC:
        for c2 in ALPHANUMERIC:
            if c1 != c2:
                word = f"{c1}{c2}{c2}{c1}"
                if word not in seen and is_valid_syntax(word):
                    seen.add(word)
                    yield word

    # x_x_ / x_y_
    for c1 in ALPHANUMERIC:
        for c2 in ALPHANUMERIC:
            word = f"{c1}_{c2}_"
            if word not in seen and is_valid_syntax(word):
                seen.add(word)
                yield word

def generate_by_pattern(pattern: str) -> Generator[str, None, None]:
    """
    Generate names according to wildcard pattern:
    '*' or '?' matches any letter or digit (a-z, 0-9)
    '#' matches any digit (0-9)
    '@' matches any letter (a-z)
    Static characters are preserved (e.g. 'vk**' -> 'vkaa', 'vka0', etc.)
    """
    pattern = pattern.lower().strip()
    char_options = []
    for ch in pattern:
        if ch in ('*', '?'):
            char_options.append(ALPHANUMERIC)
        elif ch == '#':
            char_options.append(DIGITS)
        elif ch == '@':
            char_options.append(LETTERS)
        elif ch in ALPHANUMERIC or ch == '_':
            char_options.append(ch)
        else:
            continue

    if not char_options:
        return

    for combo in itertools.product(*char_options):
        word = "".join(combo)
        if is_valid_syntax(word):
            yield word

def load_custom_wordlist(file_path: str) -> List[str]:
    """Read a custom wordlist from disk."""
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(p, "r", encoding="utf-8", errors="ignore") as f:
        words = [line.strip().lower() for line in f if line.strip()]
    
    # Filter unique and valid syntax
    valid_words = []
    seen = set()
    for w in words:
        if w not in seen and is_valid_syntax(w):
            seen.add(w)
            valid_words.append(w)
    return valid_words
