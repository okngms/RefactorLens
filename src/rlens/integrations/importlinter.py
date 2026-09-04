"""import-linter sözleşmelerinden katman beyanı okuma.

**Neden değerli:** import-linter kullanan bir proje katmanlarını **zaten
yazmıştır**. O beyanı yeniden istemek, kullanıcıya aynı bilgiyi iki yere
yazdırmak olur. v2.0 çıkarımsız çıkıyor; bu okuma sayesinde gerçek projelerde
de kullanılabilir kalıyor.

**Öncelik kuralı:** `rlens.yaml` içindeki `arch.layers` beyanı her zaman kazanır.
Kullanıcının açık tercihi bir dosya okumasıyla ezilmez.

Desteklenen kaynaklar (bu sırayla aranır):

* `pyproject.toml` → `[tool.importlinter]`
* `.importlinter`, `setup.cfg` → `[importlinter]` (INI biçimi)

Yalnızca **`layers` tipindeki** sözleşmeler okunur. `forbidden` ve
`independence` sözleşmeleri katman **sırası** vermez, dolayısıyla katman
ataması için kullanılamazlar; okunmadıkları rapora not olarak yazılır.
"""

from __future__ import annotations

import configparser
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ImportLinterContract:
    """Okunmuş bir `layers` sözleşmesi."""

    name: str
    layers: tuple[str, ...]
    """Üstten alta sıralı katman modülleri."""

    containers: tuple[str, ...] = ()
    """`containers` verilmişse katman adları buna göre nitelenir."""

    def module_prefixes(self) -> dict[str, tuple[str, ...]]:
        """Katman → modül önekleri. Nokta yol ayracına çevrilir.

        import-linter modül adı kullanır (`myapp.domain`), RefactorLens ise yol
        öneki (`myapp/domain/`). Dönüşüm burada yapılır.
        """
        result: dict[str, tuple[str, ...]] = {}
        for layer in self.layers:
            prefixes = []
            if self.containers:
                for container in self.containers:
                    prefixes.append(f"{container}.{layer}".replace(".", "/") + "/")
            else:
                prefixes.append(layer.replace(".", "/") + "/")
            result[layer.split(".")[-1]] = tuple(prefixes)
        return result


@dataclass
class ImportLinterConfig:
    """Bir projede bulunan import-linter yapılandırması."""

    source: Path | None = None
    contracts: list[ImportLinterContract] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    """Okunmayan sözleşmeler ve nedenleri. Sessiz kalmak yanıltıcı olurdu."""

    @property
    def found(self) -> bool:
        return bool(self.contracts)

    def describe(self) -> str:
        if self.source is None:
            return "no import-linter configuration found"
        names = ", ".join(c.name for c in self.contracts) or "none usable"
        return f"import-linter: {self.source.name} ({names})"


def _split_lines(value: str | list[str]) -> tuple[str, ...]:
    """INI'de çok satırlı liste, TOML'da gerçek liste gelir."""
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return tuple(line.strip() for line in value.splitlines() if line.strip())


def _contract_from(name: str, data: dict) -> tuple[ImportLinterContract | None, str]:
    kind = str(data.get("type", "")).strip()
    if kind != "layers":
        return None, f"{name}: `{kind or 'unknown'}` contracts declare no layer order"
    layers = _split_lines(data.get("layers", []))
    if len(layers) < 2:
        return None, f"{name}: fewer than two layers"
    return (
        ImportLinterContract(
            name=name,
            layers=layers,
            containers=_split_lines(data.get("containers", [])),
        ),
        "",
    )


def _read_pyproject(path: Path) -> ImportLinterConfig | None:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None
    section = data.get("tool", {}).get("importlinter")
    if not isinstance(section, dict):
        return None

    config = ImportLinterConfig(source=path)
    contracts = section.get("contracts", [])
    if isinstance(contracts, dict):
        contracts = [contracts]
    for index, raw in enumerate(contracts):
        if not isinstance(raw, dict):
            continue
        contract, reason = _contract_from(raw.get("name", f"contract {index + 1}"), raw)
        if contract:
            config.contracts.append(contract)
        elif reason:
            config.skipped.append(reason)
    return config


def _read_ini(path: Path) -> ImportLinterConfig | None:
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except (OSError, configparser.Error):
        return None
    if not any(s == "importlinter" or s.startswith("importlinter:") for s in parser.sections()):
        return None

    config = ImportLinterConfig(source=path)
    for section in parser.sections():
        if not section.startswith("importlinter:contract:"):
            continue
        data = dict(parser.items(section))
        name = data.get("name", section.split(":")[-1])
        contract, reason = _contract_from(name, data)
        if contract:
            config.contracts.append(contract)
        elif reason:
            config.skipped.append(reason)
    return config


def read_import_linter(root: Path) -> ImportLinterConfig:
    """Projede import-linter yapılandırması arar.

    Bulunmazsa boş bir yapılandırma döner — bu bir hata değildir, çoğu proje
    import-linter kullanmaz.
    """
    root = Path(root)
    candidates = [
        (root / "pyproject.toml", _read_pyproject),
        (root / ".importlinter", _read_ini),
        (root / "setup.cfg", _read_ini),
    ]
    for path, reader in candidates:
        if not path.is_file():
            continue
        config = reader(path)
        if config is not None:
            return config
    return ImportLinterConfig()


def layers_from_contracts(config: ImportLinterConfig) -> dict[str, tuple[str, ...]]:
    """Sözleşmelerden `arch.layers` biçiminde beyan üretir.

    Birden çok sözleşme varsa hepsi birleştirilir; aynı katman adı farklı
    öneklerle geçerse önekler toplanır.
    """
    declared: dict[str, list[str]] = {}
    for contract in config.contracts:
        for layer, prefixes in contract.module_prefixes().items():
            declared.setdefault(layer, []).extend(prefixes)
    return {layer: tuple(dict.fromkeys(prefixes)) for layer, prefixes in declared.items()}


def scheme_from(
    contract: ImportLinterContract,
) -> tuple[tuple[str, ...], dict[str, tuple[str, ...]]]:
    """Sözleşmeden katman şeması türetir.

    import-linter'ın `layers` semantiği nettir: liste üstten alta sıralıdır ve
    **üst katman alttakileri import edebilir, tersi yasaktır.** Bu, tam olarak
    bizim `allowed` tablomuzun tanımıdır, dolayısıyla şema doğrudan türetilir.

    Katman adları son parçadan alınır (`myapp.domain` → `domain`): şema adları
    kısa ve okunur olmalıdır, modül yolları `declared` tarafında zaten tutulur.
    """
    layers = tuple(layer.split(".")[-1] for layer in contract.layers)
    allowed = {layer: tuple(layers[index + 1 :]) for index, layer in enumerate(layers)}
    return layers, allowed


def apply_to_arch(arch, config: ImportLinterConfig):
    """import-linter beyanını `ArchConfig`'e uygular.

    **Öncelik kuralı:** `rlens.yaml` içindeki `arch.layers` her zaman kazanır.
    Kullanıcının açıkça yazdığı beyan bir dosya okumasıyla ezilmez.

    Returns:
        (yeni ArchConfig, notlar)
    """
    from dataclasses import replace

    from rlens.config import SchemeConfig

    if arch.has_declaration:
        if config.found:
            return arch, [
                "import-linter contracts found but ignored: `arch.layers` in "
                "rlens.yaml takes precedence"
            ]
        return arch, []

    if not config.found:
        return arch, []

    contract = config.contracts[0]
    notes = [f"layers read from {config.source.name}: contract `{contract.name}`"]
    if len(config.contracts) > 1:
        notes.append(
            f"{len(config.contracts) - 1} further layers contract(s) ignored; "
            f"only the first defines the scheme"
        )
    notes.extend(config.skipped)

    layers, allowed = scheme_from(contract)
    scheme = SchemeConfig(
        layers=layers,
        allowed=allowed,
        # import-linter'da alt katmana doğrudan inmek serbesttir; yalnızca
        # yukarı doğru import yasaktır. `allow_skip` bu semantiği korur.
        allow_skip=True,
    )
    declared = {
        layer.split(".")[-1]: prefixes for layer, prefixes in contract.module_prefixes().items()
    }
    return replace(arch, scheme=scheme, declared=declared), notes
