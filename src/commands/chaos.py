import os
import random

class ChaosMixin:
    def chaos_check(self):
        chaos_rate = float(os.getenv("CHAOS_RATE", "0.0"))

        if chaos_rate <= 0:
            return None  # caos desactivado

        if random.random() < chaos_rate:
            return {
                "status": "error",
                "detail": "Chaos injection forced failure"
            }

        return None
