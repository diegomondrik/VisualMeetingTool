"""Everything the program says, in each language (INGOL D-188, WI17).

Every text the application shows and every error the program raises is an
entry of one list, kept once per language: meetingtool/texts/<language>.py
holds TEXTS, {key: text}. A new language is a new file and its code in
LANGUAGES; nothing else is rewritten.

A text names the data it carries ({path}, {spent:.2f}...), with the format
of str.format. What comes from outside the program (Google's reason for
refusing a request, a system error) cannot be translated beforehand: it is
passed as External, and the text puts it inside [[ ]]. The terminal shows the
whole text in English, exactly as the commands always said it; the
application drops that part and shows the outside text below, as a detail.

A Message is the English text itself (a str), so everything that prints,
joins or compares an error as text keeps doing it, and the terminal does not
change; Message.text(language) says it in another language, and a Message
given as data to another is said in that language too.
"""

import importlib
import re
import string

LANGUAGES = ("es", "en")
DEFAULT_LANGUAGE = "es"   # the application's, until someone changes it
TERMINAL = "en"           # the commands keep speaking English
SEGMENT = re.compile(r"\[\[(.*?)\]\]", re.DOTALL)

_catalogs = {}


def catalog(language):
    """{key: text} of a language."""
    if language not in _catalogs:
        if language not in LANGUAGES:
            raise KeyError(language)
        _catalogs[language] = importlib.import_module(f"meetingtool.texts.{language}").TEXTS
    return _catalogs[language]


def is_key(value):
    return isinstance(value, str) and not isinstance(value, Message) and value in catalog(TERMINAL)


def names(text):
    """The names of the data a text carries."""
    return {field.split(".")[0].split("[")[0] for _, field, _, _ in string.Formatter().parse(text)
            if field is not None and field != ""}


def detail_names(text):
    """The names inside [[ ]]: the parts the application may show as a detail."""
    return {name for segment in SEGMENT.findall(text) for name in names(segment)}


class External(str):
    """Text that comes from outside the program; never translated."""


class Joined:
    """Several messages or values, each said in the language asked for."""

    def __init__(self, items, separator):
        self.items, self.separator = list(items), separator

    def __str__(self):
        return self.separator.join(str(item) for item in self.items)


class _Number:
    """A number formatted as its language writes it (a decimal comma in Spanish)."""

    def __init__(self, value, language):
        self.value, self.language = value, language

    def __format__(self, spec):
        text = format(self.value, spec)
        return text.replace(".", ",") if self.language == "es" and "." in text else text

    def __str__(self):
        return self.__format__("")

    def __repr__(self):
        return repr(self.value)


def _said(value, language, app, details):
    """A value given to a text, ready to be placed in it."""
    if isinstance(value, Message):
        text, found = value.render(language, app)
        details.extend(found)
        return text
    if isinstance(value, Joined):
        return value.separator.join(_said(item, language, app, details) for item in value.items)
    if isinstance(value, External):
        return str(value)
    if isinstance(value, float) and not isinstance(value, bool):
        return _Number(value, language)
    return value


def render(key, params, language, app):
    """(text, details) of an entry: in the terminal (app=False) the parts in
    [[ ]] are kept; in the application a part holding outside text is
    dropped and that text returned as a detail."""
    template = catalog(language)[key]
    details = []
    values = {name: _said(value, language, app, details) for name, value in params.items()}

    def segment(match):
        inner = match.group(1)
        outside = [name for name in names(inner) if isinstance(params.get(name), External)]
        if app and outside:
            details.extend(str(params[name]) for name in sorted(outside, key=inner.index) if str(params[name]))
            return ""
        return inner

    return SEGMENT.sub(segment, template).format_map(values), details


class Message(str):
    """An entry of the list with its data; as a str, the English text the
    terminal shows."""

    def __new__(cls, key, **params):
        text, _ = render(key, params, TERMINAL, app=False)
        message = super().__new__(cls, text)
        message.key, message.params = key, params
        return message

    def render(self, language, app=True):
        return render(self.key, self.params, language, app)

    def text(self, language):
        """What the application says, without the outside details."""
        return self.render(language)[0]

    def details(self, language):
        return self.render(language)[1]

    def __reduce__(self):
        return (_rebuild, (self.key, self.params))


def _rebuild(key, params):
    return Message(key, **params)


def said(value, language):
    """(text, details) of anything the application has to show: a Message in
    the language asked for, anything else as it is."""
    if isinstance(value, Message):
        return value.render(language)
    return str(value), []


class Failure(Exception):
    """An error of the program: its message is an entry of the list.

    Failure("key", name=value...) says the entry with that data; given a
    Message (another failure's), it says the same. Text that is not an entry
    is kept as it is: the program never raises one (tests/test_texts.py reads
    every raise), but a test may, to stand in for a failure."""

    def __init__(self, key, **params):
        if isinstance(key, Message):
            message = key
        elif is_key(key):
            message = Message(key, **params)
        else:
            message = str(key)
        self.message = message
        super().__init__(str(message))

    def text(self, language):
        return said(self.message, language)[0]

    def details(self, language):
        return said(self.message, language)[1]


def outside(error):
    """What an error says, as data for another message: a Failure's message,
    or anything else's text as outside text."""
    if isinstance(error, Failure):
        return error.message
    return External(str(error))
