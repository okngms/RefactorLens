"""messy_project'i düz bir proje gibi import edilebilir kılar.

Fikstür bilerek `src/` düzeni kullanmayan, kurulmayan küçük bir projedir —
gerçek hayatta rlens'in tarayacağı kod tabanlarının çoğu gibi. Bu yüzden
paket dizini doğrudan sys.path'e eklenir.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
