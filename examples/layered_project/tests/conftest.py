"""Katmanlı fikstürü import edilebilir kılar.

`src/` doğrudan yola eklenir; modüller `domain.entities`, `services.order_service`
gibi katman adıyla import edilir. Bu, gerçek bir src-layout projesinin yapısıdır.
"""

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
