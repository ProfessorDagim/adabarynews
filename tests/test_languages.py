from app.config import Settings
from app.services.languages import language_menu, supported_languages


def test_supported_languages_include_all_requested_languages() -> None:
    assert [language.code for language in supported_languages(Settings())] == ["en", "am", "om", "ti"]


def test_language_menu_uses_links_when_configured() -> None:
    menu = language_menu(Settings(telegram_amharic_channel_url="https://t.me/adabary_am"))
    assert menu["inline_keyboard"][1][0]["url"] == "https://t.me/adabary_am"
