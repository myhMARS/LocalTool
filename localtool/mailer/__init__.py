from localtool.core import BaseTool
from localtool.mailer.app import launch


class EmailTool(BaseTool):
    name = "email"
    help = "email client (GUI)"

    def run(self, args: list[str] | None = None) -> int:
        return launch()


run = EmailTool.entry_point
