"""Framework giriş noktaları: parametre listesi yazarın tasarımı olmayan fonksiyonlar.

Sertleştirme Blok 1b, madde 4. İki durumda bir fonksiyonun parametreleri
tasarım kararı değildir:

* **Parametreler framework'e bildirilen dış arayüzdür.** Bir click/typer
  komutunun parametreleri kullanıcının göreceği CLI seçenekleridir; bir HTTP
  route'unun parametreleri yol ve sorgu parametreleridir. Sayıyı azaltmak
  arayüzü değiştirmek demektir — "parametre nesnesi çıkar" önerisi yanlıştır.
* **Framework imzayı dikte eder.** Django sinyal alıcısı `(sender, instance,
  created, raw, using, **kwargs)` almak zorundadır; pytest fixture'ının
  parametreleri başka fixture'lardır.

Bu fonksiyonlarda `too_many_params` kokusu üretilmez ve `advise` parametre
eşiğini hedef gerekçesi saymaz (`smells.detect_function_smells`,
`advise.selector`). Metrik değişmez.

**Tanıma dar tutulur.** Yanlış pozitif, gerçek bir kokuyu gizler. Bu yüzden:

* Celery görevi (`@app.task`) giriş noktası **değildir**: parametreleri yazarın
  seçtiği mesaj içeriğidir.
* `option`/`argument` yalnızca sahibi `click`/`typer` ise ya da ilk argüman
  `-` ile başlıyorsa CLI sayılır.
* HTTP fiilleri yalnızca yol string'i `/` ile başlıyorsa route sayılır;
  `@cache.get("key")` route değildir.
* Salt dekoratör varlığı yetmez: korpusta 5+ parametreli fonksiyonların
  dekoratörlülerinin çoğu `@classmethod`, `@doc`, `@final` gibi giriş noktası
  olmayan dekoratörler taşır.

Sınıflandırma yalnızca dekoratöre bakar; tip bilgisi ya da import çözümü
kullanmaz. Bir framework metodunu override eden fonksiyon (Django
`Model.save(...)`) imzası dikte edilmiş olsa da tanınmaz — bunu görmek taban
sınıfı çözmeyi gerektirir.
"""

from __future__ import annotations

import ast

CLI = "cli"
WEB_ROUTE = "web_route"
SIGNAL_HANDLER = "signal_handler"
FIXTURE = "fixture"

KINDS = (CLI, WEB_ROUTE, SIGNAL_HANDLER, FIXTURE)

_CLI_OWNERS = frozenset({"click", "typer"})
_CLI_REGISTRATION = frozenset({"command", "group"})
_CLI_PARAMETER = frozenset({"option", "argument"})
_CLI_CONTEXT = frozenset({"pass_context", "pass_obj"})
_HTTP_ROUTE = frozenset(
    {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "trace",
        "api_route",
        "websocket",
        "route",
    }
)
_ROUTE_PATH_KEYWORDS = frozenset({"path", "rule"})
_SIGNAL = frozenset({"receiver", "listens_for"})


def _parts(decorator: ast.expr) -> tuple[str, str | None, ast.Call | None]:
    """(ad, sahip, çağrı): `@click.option(...)` → ("option", "click", <Call>)."""
    call = decorator if isinstance(decorator, ast.Call) else None
    target = call.func if call is not None else decorator
    if isinstance(target, ast.Attribute):
        owner = target.value
        owner_name = (
            owner.id
            if isinstance(owner, ast.Name)
            else (owner.attr if isinstance(owner, ast.Attribute) else None)
        )
        return target.attr, owner_name, call
    if isinstance(target, ast.Name):
        return target.id, None, call
    return "", None, call


def _first_string(call: ast.Call | None, keywords: frozenset[str] = frozenset()) -> str | None:
    if call is None:
        return None
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    for keyword in call.keywords:
        value = keyword.value
        if (
            keyword.arg in keywords
            and isinstance(value, ast.Constant)
            and isinstance(value.value, str)
        ):
            return value.value
    return None


def decorator_kind(decorator: ast.expr) -> str | None:
    """Tek bir dekoratörün işaret ettiği giriş noktası türü, yoksa `None`."""
    name, owner, call = _parts(decorator)

    if name == "fixture" and (owner == "pytest" or owner is None):
        return FIXTURE

    if name in _CLI_REGISTRATION and (owner is not None or call is not None):
        return CLI
    if name == "callback" and owner is not None and call is not None:
        return CLI
    if name in _CLI_PARAMETER:
        if owner in _CLI_OWNERS:
            return CLI
        first = _first_string(call)
        if first is not None and first.startswith("-"):
            return CLI
        return None
    if name in _CLI_CONTEXT and owner in _CLI_OWNERS | {None}:
        return CLI

    if name in _HTTP_ROUTE and call is not None:
        path = _first_string(call, _ROUTE_PATH_KEYWORDS)
        if path is not None and path.startswith("/"):
            return WEB_ROUTE
        return None

    if name in _SIGNAL and call is not None:
        return SIGNAL_HANDLER

    return None


def entry_point_kind(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Fonksiyonun giriş noktası türü; dekoratörlerinden ilk tanınan."""
    for decorator in node.decorator_list:
        kind = decorator_kind(decorator)
        if kind is not None:
            return kind
    return None
