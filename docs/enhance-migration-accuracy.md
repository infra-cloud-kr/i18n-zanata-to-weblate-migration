## 현재 구조의 문제점

현재는 문장 수와 msgid, msgstr 문자열 비교를 통해서 정합성을 검증해왔다. 그러나 번역 여부만 검증할 뿐 **번역의 문맥을 고려하지 않았습니다.** 

## 추가사항

### `msgctxt` 문자열 검증 로직 추가 

`msgctxt`는 동일한 원문 `msgid`를 **서로 다른 사용 맥락의 번역 단위로 구분하는 식별자**입니다. 예를 들어 UI에서 `Open`은 버튼 동작일 수도 있고, 상태값일 수도 있으며, 언어에 따라 번역이 달라질 수 있습니다.

```
msgctxt "button"
msgid "Open"
msgstr "열기"

msgctxt "status"
msgid "Open"
msgstr "열림"
```

`msgid` 만 검증할 경우 `msgctxt` 누락 시 기대한 결과가 나오지 않을 수 있습니다. 

## Plural Index 비교
plural은 단일 `msgstr`가 아니라 언어별 plural rule에 따라 여러 슬롯을 갖습니다. 

```
msgid "1 file"
msgid_plural "%d files"
msgstr[0] "파일 %d개"
msgstr[1] "파일 %d개"
```

PO 헤더의 `Plural-Forms`에는 `nplurals`와 각 숫자에 적용할 index를 계산하는 식이 정의됩니다. 
그러므로 마이그레이션 시 `msgfmt` 명세도 plural 엔트리에 대해 `msgid_plural` 뒤에 `msgstr[0]`부터 `msgstr[nplurals-1]`까지 중복 없이, 순서대로 있어야 합니다. 

## Fuzzy, 미번역 수 분류 강화(테)

gettext에서 fuzzy는 "번역문이 있지만 검토가 필요한 상태"로 msgfmt 컴파일에서는 fuzzy 항목을 유효하거나 번역하지 않습니다. 
이는 플랫폼 간 번역 수, 미번역 수에 영향을 미치므로, 테스트를 통해 보완해야 합니다. 

