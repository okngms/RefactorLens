<!-- Üretildi: experiments/hardening/annotations.py. Elle düzenlemeyin. -->

Scan şeması 3. Proje değeri: yuvaların havuz oranı; genel ve tür değeri projelerin medyanı (yuvalı en az 30 fonksiyonu olan projeler).

## Dağılım

| Grup | proje | kapsam | tam annotation'lı fonksiyon | hiç annotation'sız | dönüş annotation'ı |
|---|---:|---:|---:|---:|---:|
| tüm korpus | 25 | %82.4 | %75.9 | %12.8 | %69.1 |
| library | 10 | %99.5 | %99.0 | %0.6 | %99.0 |
| cli | 6 | %88.8 | %87.9 | %8.9 | %84.5 |
| web_app | 5 | %56.7 | %43.3 | %29.2 | %28.4 |
| ml_research | 4 | %54.4 | %46.7 | %42.6 | %30.0 |

## Proje başına

| Proje | tür | py.typed | kapsam | tam | hiç | dönüş |
|---|---|---|---:|---:|---:|---:|
| httpx | library | evet | %100.0 | %100.0 | %0.0 | %100.0 |
| rich | library | evet | %100.0 | %100.0 | %0.0 | %99.8 |
| fastapi | library | evet | %100.0 | %100.0 | %0.0 | %100.0 |
| flask | library | evet | %100.0 | %100.0 | %0.0 | %100.0 |
| black | cli | evet | %100.0 | %100.0 | %0.0 | %100.0 |
| mypy | cli | evet | %100.0 | %100.0 | %0.0 | %100.0 |
| pipx | cli | hayır | %100.0 | %100.0 | %0.0 | %100.0 |
| healthchecks | web_app | hayır | %100.0 | %100.0 | %0.0 | %100.0 |
| pydantic | library | evet | %99.9 | %99.9 | %0.0 | %99.6 |
| click | library | evet | %99.1 | %98.1 | %1.1 | %98.3 |
| segment-anything | ml_research | hayır | %94.0 | %91.8 | %6.9 | %92.6 |
| mealie | web_app | hayır | %87.5 | %84.6 | %8.1 | %64.2 |
| whisper | ml_research | hayır | %82.4 | %69.8 | %12.8 | %43.8 |
| httpie | cli | hayır | %77.7 | %75.9 | %17.7 | %69.1 |
| pandas | library | hayır | %66.0 | %45.3 | %24.0 | %66.4 |
| sqlalchemy | library | hayır | %62.5 | %68.9 | %31.0 | %71.9 |
| saleor | web_app | hayır | %56.7 | %43.3 | %29.2 | %28.4 |
| detectron2 | ml_research | hayır | %26.4 | %23.6 | %72.4 | %16.3 |
| attrs | library | evet | %11.4 | %10.5 | %89.5 | %7.7 |
| yt-dlp | cli | hayır | %2.2 | %2.7 | %96.9 | %1.6 |
| netbox | web_app | hayır | %2.2 | %1.4 | %97.1 | %3.6 |
| requests | library | hayır | %1.4 | %0.8 | %99.2 | %0.6 |
| redash | web_app | hayır | %1.3 | %1.7 | %98.3 | %1.4 |
| yolov5 | ml_research | hayır | %0.5 | %0.7 | %99.0 | %0.2 |
| awscli | cli | hayır | %0.2 | %0.3 | %99.6 | %0.1 |
| nanogpt | ml_research | hayır | %0.0 | %0.0 | %100.0 | %0.0 |

## Ön kayıtlı çürütme koşulları

- Genel medyan %82.4; `py.typed` taşıyan 9 projenin medyanı %100.0, taşımayan 16 projenin %59.6.
- (a) py.typed medyanı büyük değil: **hayır**
- (b) py.typed projelerinin %80'inden azı genel medyanın üstünde (8/9): **hayır**
- (c) sınıf değeri CAM'in iç kapsamından farklı: **hayır**
- Sonuç: **çürütülmedi**
