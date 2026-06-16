from .base import BaseAgent, MODEL_SMART

SCREENSHOT_SYSTEM = (
    "Ты описываешь UI-макет для генерации кода. Опиши верстку, секции, цвета, "
    "компоненты, расположение. По-русски, структурировано."
)


class ScreenshotAgent(BaseAgent):
    name = 'screenshot'
    model = MODEL_SMART

    def describe(self, image_b64: str) -> str:
        return self.run_vision(SCREENSHOT_SYSTEM, image_b64, model=MODEL_SMART, max_tokens=1500)
