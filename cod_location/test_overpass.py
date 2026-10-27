# import time
# import urllib.parse
# import urllib.request

# ENDPOINTS = [
#     "https://overpass-api.de/api/interpreter",
#     "https://z.overpass-api.de/api/interpreter",
#     "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
#     "https://overpass.private.coffee/api/interpreter",
#     "https://overpass.kumi.systems/api/interpreter",
# ]

# UA = "ShareSpace/1.0 (proyek kuliah PBP; kontak: taufikramadhan662@gmail.com)"

# VARIANTS = {
#     "UA + Referer": {"User-Agent": UA, "Referer": "https://github.com/pbp-kelompok-B05/ShareSpace", "Accept": "*/*"},
#     "UA saja": {"User-Agent": UA, "Accept": "*/*"},
# }

# QUERY = '[out:json][timeout:10];nwr(around:500,-6.3653,106.8315)["amenity"="library"]["name"];out center tags 10;'
# body = urllib.parse.urlencode({"data": QUERY}).encode()

# for endpoint in ENDPOINTS:
#     for label, headers in VARIANTS.items():
#         req = urllib.request.Request(endpoint, data=body, headers=headers)
#         start = time.time()
#         try:
#             with urllib.request.urlopen(req, timeout=10) as resp:
#                 print(f"OK    [{label}] {endpoint}  HTTP {resp.status}  {time.time()-start:.1f}s")
#         except Exception as error:
#             print(f"GAGAL [{label}] {endpoint}  {type(error).__name__}: {error}  {time.time()-start:.1f}s")