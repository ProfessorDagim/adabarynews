from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class LanguageOption:
    code: str
    label: str
    native_label: str
    destination_url: str | None


def supported_languages(settings: Settings) -> list[LanguageOption]:
    """Describe the reader-facing language menu without exposing private IDs."""
    return [
        LanguageOption("en", "English", "English", None),
        LanguageOption("am", "Amharic", "አማርኛ", settings.telegram_amharic_channel_url),
        LanguageOption("om", "Afaan Oromo", "Afaan Oromo", settings.telegram_oromo_channel_url),
        LanguageOption("ti", "Tigrinya", "ትግርኛ", settings.telegram_tigrinya_channel_url),
    ]


def language_menu(settings: Settings) -> dict[str, object]:
    """Build an inline-keyboard-compatible menu for a bot or web interface."""
    buttons = []
    for language in supported_languages(settings):
        button: dict[str, str] = {"text": f"{language.native_label} · {language.label}"}
        if language.destination_url:
            button["url"] = language.destination_url
        else:
            button["callback_data"] = f"language:{language.code}"
        buttons.append([button])
    return {"text": "Choose the language you want to read news in:", "inline_keyboard": buttons}
