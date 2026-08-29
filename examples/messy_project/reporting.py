"""Gri bölge vakası: kısmi annotation + orta düzey kohezyonsuzluk.

Bu sınıf CAM eşiğinin (`metrics.cam_min_annotation_coverage`, varsayılan 0.7)
**altında** kalacak şekilde tasarlandı: annotate parametre oranı 1/3 ≈ 0.33.
Amaç, eşiğin gerçekten çalıştığını ve "biraz annotation var" durumunda aracın
CAM'i zorlamadığını kanıtlamak.

Ayrıca LCOM4 = 2: gövde tamponu (`_lines`) ile sunum ayarları
(`_title`, `_width`) birbirine hiç dokunmaz.
"""


class ReportBuilder:
    def __init__(self):
        self._lines = []
        self._title = "Report"
        self._width = 40

    # Bileşen 1 — gövde tamponu
    def add_line(self, text: str) -> None:
        self._lines.append(text)

    def render(self):
        return "\n".join(self._lines)

    def reset(self):
        self._lines = []

    # Bileşen 2 — sunum ayarları
    def set_title(self, title):
        self._title = title

    def set_width(self, width):
        if width < 1:
            raise ValueError("genislik pozitif olmali")
        self._width = width

    def header(self):
        return self._title.center(self._width, "-")
