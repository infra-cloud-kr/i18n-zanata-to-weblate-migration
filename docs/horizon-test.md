# Horizon 1차 테스트 보고서 — Zanata → Weblate 번역 이관 검증

## 요약

Horizon 프로젝트의 `stable/2025.1` 브랜치를 대상으로 Zanata → Weblate 번역 이관 결과를 검증했습니다. 검증 과정에서 아래 3가지 유형의 문제를 확인했습니다.

| # | 문제 유형 | 대상 컴포넌트 | 영향 |
|---|---|---|---|
| 1 | 번역 전체 미반영 (빈 자동 생성 파일) | `releasenotes`, `openstack-dashboard-django` 등 | 번역 수천 건 손실 |
| 2 | fuzzy 번역 소실 | `releasenotes` (`fr`) | fuzzy 번역 2건 소실 |
| 3 | plural index 구조 손실 | `openstack-dashboard-django` (`kn`) | plural 항목 구조 불일치 |
| 4 | trailing ellipsis 자동 치환 | `openstack-dashboard-djangojs` (`id`, `ru`) | 문장부호 표기 변경 |

1~3번은 업로드 시 `method=translate` 방식을 사용한 데 따른 구조적 원인으로 판단되며, 4번은 Weblate의 자동 수정(fixup) 기능이 정상 동작한 것으로 판단됩니다.

---

## 1. `releasenotes` 컴포넌트 — 번역 전체 미반영

### 결론

`stable/2025.1`의 `releasenotes` 컴포넌트에서 일부 로케일의 PO 번역이 Weblate에 반영되지 않았습니다. 검증 오류는 오탐이 아닙니다. Weblate 파일에는 925개 source 항목이 정상 생성됐지만, 일부 로케일은 기존 `msgstr`가 전부 비어 있는 **자동 생성 번역 파일** 상태입니다.

추가로 `fr` 로케일은 fuzzy 상태였던 번역 2건이 빈 번역으로 변경되었습니다.

### 대상 경로

| 구분 | 경로 |
|---|---|
| Zanata 원본 PO | `.../translations/releasenotes/source/locale/<locale>/LC_MESSAGES/releasenotes.po` |
| Weblate 검증 PO | `.../test/horizon/stable-2025-1/releasenotes/source/locale/<locale>/LC_MESSAGES/releasenotes.po` |

### 손실 현황

| 로케일 | Zanata 번역 수 | Weblate 번역 수 | 미번역 증가 | 상태 |
|---|---|---|---|---|
| `eo` | 24 | 0 | +24 | 전체 번역 미반영 |
| `zh_TW` | 12 | 0 | +12 | 전체 번역 미반영 |
| `en_GB` | 924 | 0 | +924 | 전체 번역 미반영 |
| `de` | 652 | 0 | +652 | 전체 번역 미반영 |
| `id` | 859 | 0 | +859 | 전체 번역 미반영 |
| `fr` | 38 + fuzzy 2 | 38 + fuzzy 0 | +2 | fuzzy 번역 2건 소실 |

`eo`, `zh_TW`, `en_GB`, `de`, `id`의 Weblate PO 헤더는 모두 아래와 같이 표시됩니다.

```
Last-Translator: Automatically generated
```

즉 Weblate가 source POT에서 새로 생성한 빈 translation 파일이며, 원본 PO 업로드 내용이 반영된 파일이 아닙니다.

### 실제 `msgid` 손실 사례

**`eo`: 24건 중 1건**

```po
msgid "\"Interfaces\" tab is added to the instance detail page. ..."

# Zanata 원본
msgstr "\"Interfacoj\" langeto estas aldonita al la apero detala paĝo. ..."

# Weblate stable/2025.1 결과
msgstr ""
```

**`en_GB`: 924건 중 1건**

```po
msgid "\"Interfaces\" tab is added to the instance detail page. ..."

# Zanata 원본
msgstr "\"Interfaces\" tab is added to the instance detail page. ..."

# Weblate stable/2025.1 결과
msgstr ""
```

**`de`: 652건 중 1건**

```po
msgid "(optional) Use the common Angular template as the basis of any Angular pages ..."

# Zanata 원본
msgstr "(Optional) Verwenden der allgemeinen Angular-Vorlage als Basis aller Angular-Seiten ..."

# Weblate stable/2025.1 결과
msgstr ""
```

**`id`: 859건 중 1건**

```po
msgid "\"Interfaces\" tab is added to the instance detail page. ..."

# Zanata 원본
msgstr "Tab \"Interfaces\" ditambahkan ke halaman detail instance. ..."

# Weblate stable/2025.1 결과
msgstr ""
```

**`zh_TW`: 12건 중 1건**

```po
msgid "10.0.0"

# Zanata 원본
msgstr "10.0.0"

# Weblate stable/2025.1 결과
msgstr ""
```

### `fr` fuzzy 번역 소실 사례

Zanata에서 fuzzy 번역문이 있었던 아래 두 항목은, Weblate에서 fuzzy 플래그와 번역문이 모두 사라졌습니다.

```po
msgid "A directive (hz-details) provides the ability to intelligently display a set of views ..."

# Zanata
#, fuzzy
msgstr "Une directive (hz-details) permet d'afficher intelligemment un ensemble de vues ..."

# Weblate stable/2025.1
msgstr ""
```

```po
msgid "A generic Details display parses the location to determine the resource type ..."

# Zanata
#, fuzzy
msgstr "Un affichage générique Details analyse l'emplacement pour déterminer le type de ressource ..."

# Weblate stable/2025.1
msgstr ""
```

### 원인

**① 일부 기존 Weblate translation에 원본 PO가 반영되지 않음**

Weblate에는 해당 로케일 translation이 존재하지만, 내용은 자동 생성된 빈 파일입니다. 아래 중 하나가 발생한 것으로 판단됩니다.

- 해당 로케일의 PO 업로드가 실행되지 않음
- PO 업로드가 실패했지만 실패 상태가 후속 처리에서 충분히 드러나지 않음
- 업로드 후 빈 자동 생성 파일로 덮어써짐

동일 원본 데이터가 `stable/2025.2`에서는 정상 반영된 사례가 있으므로, Zanata 원본 파일 자체의 문제는 아닙니다.

**② `translate` 업로드 방식이 fuzzy 번역을 보존하지 못함**

현재 업로드 구현은 아래처럼 `translate` 방식을 고정 사용합니다.

```json
"data": {"method": "translate"}
```

이 방식은 빈 translation에 일반 번역을 채우는 용도에는 맞지만, fuzzy 번역을 복구·보존하는 방식으로는 적합하지 않습니다. `fr`의 fuzzy 2건 소실이 그 증거입니다.

### 영향

- `en_GB` 번역 924건이 실제로 미이관되었습니다.
- `id` 859건, `de` 652건 등 총 2,471건의 일반 번역이 Weblate에 반영되지 않았습니다.
- `fr` fuzzy 번역 2건이 소실되었습니다.
- 이 상태에서 Weblate를 번역 원본으로 사용하면, 기존 Zanata 번역이 사라진 상태로 운영될 위험이 있습니다.

---

## 2. `openstack-dashboard-django` (`kn`) — plural index 구조 손실

### 결론

Zanata PO를 원본 기준으로 보존하는 것이 목표라면, 현재의 `method=translate` 업로드 방식은 적절하지 않습니다.

`translate`는 번역문만 기존 Weblate 문자열에 적용하는 방식입니다. 원본 PO의 fuzzy 플래그, 빈 plural index, 헤더·주석 같은 파일 구조까지 보존하려면 `method=replace`로 원본 PO 전체를 업로드해야 합니다.

참고 문서:

- [Weblate 업로드 방식](https://docs.weblate.org/en/weblate-2026.8/user/files.html)
- [Weblate REST API 업로드 endpoint](https://docs.weblate.org/en/weblate-5.13/api.html)
- [Weblate Gettext PO 지원](https://docs.weblate.org/en/latest/formats/gettext.html)

### 실제 사례: `stable/2025.1 / openstack-dashboard-django / kn`

| 항목 | Zanata | Weblate `stable/2025.1` | 정상 이관된 `stable/2025.2` |
|---|---|---|---|
| 전체 항목 | 2,456 | 2,456 | 2,456 |
| 번역됨 | 1,186 | 0 | 1,186 |
| 미번역 | 1,270 | 2,456 | 1,270 |
| plural 항목 | 123 | 123 | 123 |

`stable/2025.1` Weblate 파일은 `Last-Translator: Automatically generated` 상태입니다. translation은 생성됐지만 Zanata 원본 PO가 반영되지 않은 빈 파일입니다.

```po
msgid "Unable to parse IP address %s."

# Zanata 원본
msgstr "IP ವಿಳಾಸ %s ಅನ್ನು ಪಾರ್ಸ್ ಮಾಡಲು ಸಾಧ್ಯವಾಗಿಲ್ಲ."

# Weblate stable/2025.1
msgstr ""
```

이는 공백이나 표시 차이가 아닌, 1,186개 번역의 실제 미이관입니다.

### plural index 차이

Zanata 원본에는 아래처럼 빈 값도 포함해 plural index가 존재합니다.

```po
msgid "Delete Host Aggregate"
msgid_plural "Delete Host Aggregates"
msgstr[0] ""
msgstr[1] ""
```

정상 이관된 `stable/2025.2`도 동일합니다.

```po
msgid "Delete Host Aggregate"
msgid_plural "Delete Host Aggregates"
msgstr[0] ""
msgstr[1] ""
```

하지만 원본이 반영되지 않은 `stable/2025.1` 자동 생성 PO에는 아래만 있습니다.

```po
msgid "Delete Host Aggregate"
msgid_plural "Delete Host Aggregates"
msgstr[0] ""
```

따라서 검증기는 `[0, 1]`과 `[0]`의 차이를 `Plural form count mismatch`로 보고합니다.

값이 일부만 있는 plural 항목도 원본 구조를 보존해야 합니다.

```po
msgid "Delete Volume"
msgid_plural "Delete Volumes"

# Zanata 원본 및 정상 이관된 stable/2025.2
msgstr[0] "ಪರಿಮಾಣಗಳನ್ನು  ಅಳಿಸಿ "
msgstr[1] ""

# 이관 실패한 stable/2025.1
msgstr[0] ""
```

### 원인

현재 업로드 구현은 아래와 같습니다.

```json
"data": {"method": "translate"}
```

Weblate 문서에 따르면 `translate`는 업로드 파일의 "번역문만" 기존 문자열에 추가합니다. 즉 원본 PO 전체를 그대로 이관하는 방식이 아닙니다.

특히 다음을 보존해야 하는 마이그레이션에는 부족합니다.

- fuzzy 플래그
- `msgstr[n]` index 구조
- PO 헤더와 주석
- 원본의 빈 plural form 표현

### 권장 마이그레이션 방식

1. POT로 Weblate component를 생성합니다.
2. 대상 언어 translation을 생성합니다.
3. Zanata 원본 PO와 Weblate POT의 `msgid`/`msgctxt` 집합이 일치하는지 확인합니다.
4. 현재 Weblate PO를 백업합니다.
5. 원본 Zanata PO를 `method=replace`로 업로드합니다.

   ```json
   "data": {"method": "replace"}
   ```

6. Weblate에서 다시 PO를 다운로드합니다.
7. 아래 항목을 Zanata 원본과 비교합니다.

   | 검증 항목 | 기대값 |
   |---|---|
   | `msgid` / `msgctxt` | 동일 |
   | `msgstr` / `msgstr[n]` | 동일 |
   | plural index 집합 | 동일 |
   | fuzzy 플래그 | 동일 |
   | 번역/미번역/fuzzy 수 | 동일 |
   | PO 형식 검사 | 통과 |

### 주의사항

`replace`는 기존 translation 파일 전체를 바꾸므로, Weblate에서 작업 중인 번역을 덮어쓸 수 있습니다. 따라서 신규 이관 대상 또는 현재처럼 빈 자동 생성 파일에만 사용하고, 업로드 전 백업과 POT-PO 항목 비교를 반드시 수행해야 합니다.

---

## 3. `openstack-dashboard-djangojs` — trailing ellipsis 자동 치환

### 결론

`Trailing ellipsis replacer` fixup이 적용된 것으로 판단되는 실제 사례를 확인했습니다. 이는 데이터 손실이 아니라 Weblate의 정상 자동 수정 동작으로 판단됩니다.

### 대상 파일

```
Zanata:
.../translations/openstack_dashboard/locale/id/LC_MESSAGES/djangojs.po

Weblate:
.../test/horizon/stable-2025-1/openstack-dashboard-djangojs/locale/id/LC_MESSAGES/djangojs.po
```

### 사례 (`id` 로케일, 5건)

| msgid | Zanata 번역 | Weblate 번역 |
|---|---|---|
| `"One fine body…"` | `"Satu tubuh baik saja ..."` | `"Satu tubuh baik saja …"` |
| `"One small body…"` | `"Satu tubuh kecil ..."` | `"Satu tubuh kecil …"` |
| `"One tiny body…"` | `"Satu tubuh kecil ..."` | `"Satu tubuh kecil …"` |
| `"One large body…"` | `"Satu tubuh besar ..."` | `"Satu tubuh besar …"` |
| `"One super large body…"` | `"Satu tubuh super besar ..."` | `"Satu tubuh super besar …"` |

다섯 건 모두 같은 패턴입니다.

```
msgid:          …  (U+2026, 말줄임표)
Zanata msgstr:  ... (U+002E × 3, 마침표 3개)
Weblate msgstr: …  (U+2026, 말줄임표)
```

이는 Weblate 문서에 명시된 "source string과 일치시키기 위해 trailing dots를 ellipsis로 교체"하는 동작과 정확히 일치합니다. 따라서 이관 중 해당 automatic fixup이 실행된 것으로 판단할 근거가 충분합니다.

참고: [Checks and fixups — Weblate 5.8.3 documentation](https://docs.weblate.org/no/weblate-5.8.3/user/checks.html#trailing-ellipsis-replacer)

추가로 아래와 같이 trailing whitespace가 제거된 사례도 함께 관찰되었습니다.

```po
# Zanata
msgstr "Нестилизованный "

# Weblate
msgstr "Нестилизованный"
```

---

## 종합 결론 및 조치 방향

| 문제 | 원인 | 조치 방향 |
|---|---|---|
| 번역 전체 미반영 (`releasenotes`, `openstack-dashboard-django` 등) | 일부 로케일 PO 업로드 누락/실패 또는 빈 자동 생성 파일로 덮어씀 | 업로드 성공 여부를 로케일 단위로 검증하는 절차 추가 |
| fuzzy 번역 소실 | `method=translate` 방식이 fuzzy 플래그를 보존하지 않음 | `method=replace`로 전환 |
| plural index 구조 손실 | `method=translate` 방식이 원본 PO 구조(빈 plural 포함)를 보존하지 않음 | `method=replace`로 전환 + 업로드 전후 POT-PO 비교 |
| trailing ellipsis 치환 | Weblate 자동 fixup(정상 동작) | 별도 조치 불필요, 검증 시 예외로 처리 |

**공통 권장 사항:** 업로드 방식을 `method=translate`에서 `method=replace`로 전환하고, 업로드 전 백업 및 업로드 후 Zanata 원본과의 `msgid`/`msgstr`/plural/fuzzy 비교 검증을 마이그레이션 절차에 포함합니다.
