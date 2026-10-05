## Fuzzy 미번역 문제
gettext의 `fuzzy` 플래그는 "번역문은 있지만 검토가 필요한 상태"를 뜻한다.
Zanata에서 fuzzy로 분류돼 있던 항목이 Weblate 업로드 과정에서 fuzzy 표시와
번역 내용이 함께 사라져 **미번역(untranslated)으로 재분류**되는 문제가 있었다.


### 예시
- **프로젝트**: horizon
- **카테고리**: Fuzzy → 미번역 오분류
- **컴포넌트**: releasenotes
- **로케일**: fr (프랑스어)

```po
msgid ""
"A directive (hz-details) provides the ability to intelligently display a set"
" of views (typically for a Details context)."

# Zanata 원본
#, fuzzy
msgstr ""

# Weblate 결과 (fuzzy=process 적용 전)
# (#, fuzzy 주석 자체가 사라짐)
msgstr ""
```

### 해결방안 
- `fuzzy: 'process'` 속성을 업로드 요청 API에 추가

## Plural Index(복수형 슬롯) 손실
gettext PO에서 복수형(plural)이 있는 항목은 단일 `msgstr`가 아니라 `msgstr[0]`, `msgstr[1]`, ... 형태의 언어별 슬롯(`msgstr_plural`)을 갖는다.
슬롯 개수(nplurals)는 언어마다 다르다(헝가리어 2개, 아랍어 6개 등). 마이그레이션 후 Weblate 쪽에서 **이 슬롯 개수 자체가 Zanata 원본보다 적게(대부분 1개로) 줄어드는 문제**가 대량 발생했다.

### 예시
- **프로젝트**: horizon
- **카테고리**: Plural form count mismatch (슬롯 손실)
- **컴포넌트** openstack-dashboard-django
- **로케일**: hu (헝가리어, nplurals=2)

```po
# Zanata 원본
msgid "Delete Volume"
msgid_plural "Delete Volumes"
msgstr[0] ""
msgstr[1] ""
```

```po
# Weblate stable/2025.1 다운로드 결과
msgid "Delete Volume"
msgid_plural "Delete Volumes"
msgstr[0] ""
```

### 해결 방안
- `_wait_for_translation_plural_ready()` 추가 —  plural 유닛의 target 슬롯
개수가 언어 nplurals와 같아질 때까지 대기 ([PR #28](https://github.com/openstack-kr/i18n-zanata-to-weblate-migration/pull/28 ))

## Weblate Automatic Fixup으로 인한 번역 내용 불일치
Weblate 서버는 번역을 저장할 때 "automatic fixup"(자동 정리) 규칙에 따라 문자열을 표준 형태로 다듬는다. 이 저장소의 정합성 검사는 Zanata 원본 `msgstr`와 Weblate 저장 결과 `msgstr`를 문자 단위로 그대로 비교(`==`)하기때문에, 아래 다섯 가지 fixup이 켜져 있으면 **내용은 완전히 동일한데 표기만 바뀐 것**까지 전부 "Translation mismatch"(또는 더 심각하게는 "Placeholder mismatch")로 잘못 보고된다.

### 예시 1. Trailing and leading whitespace fixer
- **프로젝트**: horizon
- **카테고리**: Automatic fixup — 앞뒤 공백 제거
- **컴포넌트**: openstack-dashboard-django
- **로케일**: es (스페인어)

```po
# Zanata 원본
msgid "Availability Zone"
msgstr "Zona de Disponibilidad "
```

```po
# Weblate 다운로드 결과
msgid "Availability Zone"
msgstr "Zona de Disponibilidad"
```

### 예시 2. Trailing ellipsis replacer
- **프로젝트**: horizon
- **카테고리**: Automatic fixup — `...` → `…` 치환
- **컴포넌트**: openstack-dashboard-djangojs
- **로케일**: eo (에스페란토)

```po
# Zanata 원본
msgid "One fine body…"
msgstr "Unu fajna korpo ..."
```

```po
# Weblate 다운로드 결과
msgid "One fine body…"
msgstr "Unu fajna korpo …"
```

### 예시 3. Zero-width space removal
- **프로젝트**: horizon
- **카테고리**: Automatic fixup — zero-width space(U+200B) 제거
- **컴포넌트**: openstack-dashboard-django
- **로케일**: es (스페인어)

```po
# Zanata 원본
msgid ""
"IP address of Gateway (e.g. 192.168.0.254) If you do not want to use a "
"gateway, check 'Disable Gateway' below."
msgstr ""
"Dirección IP de la puerta de enlace (por ejemplo, 192.168.0.254). Si no "
"desea utilizar una puerta de enlace, consulte 'Desactivar puerta de enlace' "
"a ​​continuación."
```
Zanata 번역문의 `a`와 `continuación` 사이에 zero-width space(U+200B) 두 개가 끼어 있었는데(코드 블록에서는 눈에 보이지 않는 문자로 남아있다), Weblate가 저장 시 이를 제거했다.
```po
# Weblate 다운로드 결과
msgstr ""
"Dirección IP de la puerta de enlace (por ejemplo, 192.168.0.254). Si no "
"desea utilizar una puerta de enlace, consulte 'Desactivar puerta de enlace' "
"a continuación."
```

### 예시 4. Devanagari danda
- **프로젝트**: horizon
- **카테고리**: Automatic fixup — 마침표(`.`) → danda(`।`) 치환
- **컴포넌트**: openstack-dashboard-django
- **로케일**: hi (힌디어)

```po
# Zanata 원본 (openstack_dashboard/api/neutron.py:2265)
msgid "Unable to connect to Neutron."
msgstr "न्यूट्रॉन से जुड़ नहीं सका."
```

문장 끝의 마침표(`.`, U+002E)가 데바나가리 문장부호 danda(`।`, U+0964)로 치환됐다.
```po
# Weblate 다운로드 결과 (openstack_dashboard/api/neutron.py:2300)
msgid "Unable to connect to Neutron."
msgstr "न्यूट्रॉन से जुड़ नहीं सका।"
```

### 예시 5. Punctuation spacing
이 fixup은 다른 네 개와 달리 **내용이 그대로인 표기 정규화가 아니라 실제 런타임 오류로 이어질 수 있는 콘텐츠 변형**을 일으킬 수 있어 검사 심각도가 "Translation mismatch"가 아닌 "Placeholder mismatch"로 별도
분류된다.

- **프로젝트**: horizon
- **카테고리**: Automatic fixup — 프랑스어 문장부호 간격(non-breaking space) 삽입
- **컴포넌트**: horizon-djangojs
- **로케일**: fr (프랑스어)

```po
# Zanata 원본
msgid "Load {$ ::title $} from a file"
msgstr "Charger {$ ::title $} depuis un fichier"
```

```po
# Weblate 다운로드 결과 (화면상으로는 동일해 보이지만 바이트가 다름)
msgid "Load {$ ::title $} from a file"
msgstr "Charger {$ ::title $} depuis un fichier"
```

`xxd`로 `msgstr`의 `{$ ::title` 부분을 바이트 단위로 대조하면:

```
# Zanata: { $ <space> : : t i t l e   (0x20 = 일반 공백)
# Weblate: { $ <U+00A0> : : t i t l e  (0xC2 0xA0 = non-breaking space)
```

### 해결 방안
- Weblate Server에 아래의 flag를 모두 비활성화

### 제거할 플래그 목록: 
1. Trailing ellipsis replacer (chars.ReplaceTrailingDotsWithEllipsis)
2. Zero-width space removal (chars.RemoveZeroSpace)
3. Trailing and leading whitespace fixer (whitespace.SameBookendingWhitespace)
4. Devanagari danda (chars.DevanagariDanda)
5. Punctuation spacing (chars.PunctuationSpacing, ignore-punctuation-spacing 플래그 관련)

### 관련 링크
- https://docs.weblate.org/en/latest/user/checks.html