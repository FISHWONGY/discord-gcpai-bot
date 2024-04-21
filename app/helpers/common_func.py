import json
import re
import string
import random


class Helpers:
    def __init__(self) -> None:
        self.characters = string.ascii_letters + string.digits

    @staticmethod
    def extract_json_string(s: str) -> dict:
        start_index = s.index("{")
        end_index = s.rindex("}") + 1
        json_str = s[start_index:end_index]
        json_str = json_str.replace("\n", " ")
        json_dict = json.loads(json_str)

        return json_dict

    def get_file_suffix(self, keyword: str) -> str:
        random_str = "".join(
            random.choice(self.characters) for _ in range(random.randint(3, 5))
        )
        res = re.split(r"\W", keyword)[0]
        return f"{res}_{random_str}"
