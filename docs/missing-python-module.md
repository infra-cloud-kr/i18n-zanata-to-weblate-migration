## 문제 상황

- aodh, ceilometer, designate, ironic, neutron, neutron-lib, nova, watcher, python-heatclient, python-openstackclient, oslo.* 이 프로젝트들이 8월에 검증했을 때를 비교해서 모듈 컴포넌트가 생략되는 문제가 있음
  - watcher, oslo.*는 아직 미확인

## 문제 원인

- setup.cfg에서 pyproject.toml로 전환되면서, 파이썬 도메인 대상으로 pot가 정상적으로 추출되지 않았다. 이로 인해 upstream-translation-update 시 zanata에서 obsolete docs로 적용되면서 Zanata 상에 보여지지 않았다.
  - zanata에서 obsolete docs 문서가 되면, 아무에게도 보여지지 않게 된다.

> the relative path `messages/kdeedu/kalzium.pot` will be the document's unique identifier inside Zanata. If you change `src-dir` setting later, e.g. to ".", which results in a change of the relative path to `templates/messages/kdeedu/kalzium.pot`, pushing again will create a new document with the new path as its unique identifier, and the old document will be considered obsolete and will not be visible to anyone. The old document's translations will not be copied to the new document automatically, but they will appear as Translation Memory matches. This can be confusing and frustrating for translators.
>
> - [https://docs.zanata.org/en/release/client/configuration/](https://docs.zanata.org/en/release/client/configuration/)



## 프로젝트 별 분석


### 분석 방법

- pyproject.toml 업데이트 머지 시간 전후를 기준으로 `upstream-translation-update` 결과를 분석한다. 이후 파이썬 도메인의 모듈이 정상적으로 추출되었는지 확인한다.

### aodh

#### 타임라인


| 시각 (UTC)         | 링크                                                                                                                                    | 영향                                                                                     |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| 2026-09-21 11:22 | [`aodh:a47c236b`](https://review.opendev.org/q/I51526bf3ba53996924fc940616bb81e9cc1edea0)                                             | `setup.cfg`의 `[files]` 등이 삭제되고 `pyproject.toml`에 `[tool.setuptools.packages.find]`가 생김 |
| 2026-09-21 14:22 | [`upstream-translation-update` 실행 로그](https://zuul.opendev.org/t/openstack/build/8d3f11401ef0433594fd08e1d395b723/log/job-output.txt) | Zanata `master` 버전의 `aodh/locale/aodh`가 obsolete로 바뀜                                   |


#### upstream-translation-update 로그 분석

- pyproject.toml가 변경된 시점으로부터 파이썬 도메인이 `find` 로 추출되는 것을 확인할 수 있다. 
- 2026-09-21
  - [https://zuul.opendev.org/t/openstack/build/8d3f11401ef0433594fd08e1d395b723/log/job-output.txt](https://zuul.opendev.org/t/openstack/build/8d3f11401ef0433594fd08e1d395b723/log/job-output.txt)

```
2026-09-21 14:22:01.263840 | ubuntu-noble | + rm -rf releasenotes/work
2026-09-21 14:22:01.266217 | ubuntu-noble | + ALL_MODULES='releasenotes '
2026-09-21 14:22:01.266251 | ubuntu-noble | + for modulename in $module_names
2026-09-21 14:22:01.266258 | ubuntu-noble | + extract_messages_python find
2026-09-21 14:22:01.266264 | ubuntu-noble | + local modulename=find
2026-09-21 14:22:01.266274 | ubuntu-noble | + local pot=find/locale/find.pot
2026-09-21 14:22:01.266281 | ubuntu-noble | + mkdir -p find/locale
2026-09-21 14:22:01.268542 | ubuntu-noble | + pybabel --quiet extract --add-comments Translators: --msgid-bugs-address=https://bugs.launchpad.net/openstack-i18n/ --project=aodh --version= -k _C:1c,2 -k _P:1,2 -o find/locale/find.pot find
2026-09-21 14:22:01.365091 | ubuntu-noble | + check_empty_pot find/locale/find.pot
2026-09-21 14:22:01.365151 | ubuntu-noble | + local pot=find/locale/find.pot
2026-09-21 14:22:01.365908 | ubuntu-noble | ++ msgfmt --statistics -o /dev/null find/locale/find.pot
2026-09-21 14:22:01.371446 | ubuntu-noble | + trans='0 translated messages.'
2026-09-21 14:22:01.371493 | ubuntu-noble | + '[' '0 translated messages.' = '0 translated messages.' ']'
2026-09-21 14:22:01.371501 | ubuntu-noble | + rm find/locale/find.pot
2026-09-21 14:22:01.373261 | ubuntu-noble | + git rm --ignore-unmatch find/locale/find.pot
2026-09-21 14:22:01.376667 | ubuntu-noble | + ALL_MODULES='find releasenotes '
...
2026-09-21 14:22:03.292264 | ubuntu-noble | [INFO]            releasenotes/source/locale/releasenotes
2026-09-21 14:22:03.376923 | ubuntu-noble | [WARN] Found 1 obsolete docs on the server which will be DELETED # obsolete docs 감지
2026-09-21 14:22:03.376978 | ubuntu-noble | [INFO] Obsolete docs: [aodh/locale/aodh]
```


- 2026-09-09 (09-21일 이전 마지막 빌드 시각)
- [https://zuul.opendev.org/t/openstack/build/1613af88efd446a788c4c265eae06b8c/log/job-output.txt](https://zuul.opendev.org/t/openstack/build/1613af88efd446a788c4c265eae06b8c/log/job-output.txt)

```
2026-09-09 17:27:37.951916 | ubuntu-noble | + ALL_MODULES='releasenotes '
2026-09-09 17:27:37.951940 | ubuntu-noble | + for modulename in $module_names
2026-09-09 17:27:37.951951 | ubuntu-noble | + extract_messages_python aodh
2026-09-09 17:27:37.951966 | ubuntu-noble | + local modulename=aodh
2026-09-09 17:27:37.951976 | ubuntu-noble | + local pot=aodh/locale/aodh.pot
2026-09-09 17:27:37.951988 | ubuntu-noble | + mkdir -p aodh/locale
2026-09-09 17:27:37.954431 | ubuntu-noble | + pybabel --quiet extract --add-comments Translators: --msgid-bugs-address=https://bugs.launchpad.net/openstack-i18n/ --project=aodh --version= -k _C:1c,2 -k _P:1,2 -o aodh/locale/aodh.pot aodh
2026-09-09 17:27:38.360627 | ubuntu-noble | + check_empty_pot aodh/locale/aodh.pot
2026-09-09 17:27:38.360756 | ubuntu-noble | + local pot=aodh/locale/aodh.pot
2026-09-09 17:27:38.361424 | ubuntu-noble | ++ msgfmt --statistics -o /dev/null aodh/locale/aodh.pot
2026-09-09 17:27:38.367671 | ubuntu-noble | + trans='0 translated messages, 33 untranslated messages.'
2026-09-09 17:27:38.367708 | ubuntu-noble | + '[' '0 translated messages, 33 untranslated messages.' = '0 translated messages.' ']'
2026-09-09 17:27:38.367761 | ubuntu-noble | + ALL_MODULES='aodh releasenotes '
...
2026-09-09 17:27:40.470462 | ubuntu-noble | [INFO] Found source documents:
2026-09-09 17:27:40.470548 | ubuntu-noble | [INFO]            aodh/locale/aodh
2026-09-09 17:27:40.470561 | ubuntu-noble | [INFO]            releasenotes/source/locale/releasenotes
```


### ceilometer

- [https://opendev.org/openstack/ceilometer/commit/4b1d7b2bce2f4093fc2e577a4a118e8f181f14ad](https://opendev.org/openstack/ceilometer/commit/4b1d7b2bce2f4093fc2e577a4a118e8f181f14ad)

#### 로그 분석

- 위와 동일하게 pyproject.toml가 변경된 이후로부터 파이썬 도메인이 find로 추출되면서 ceilometer가 obsolete docs 문서가 되었다. 
- 2026-09-21
  - [https://zuul.opendev.org/t/openstack/build/60fa03c8b4c04444a5d46d4b033b88cf/log/job-output.txt](https://zuul.opendev.org/t/openstack/build/60fa03c8b4c04444a5d46d4b033b88cf/log/job-output.txt)

```
2026-09-21 11:26:00.585575 | ubuntu-noble | + ALL_MODULES='releasenotes '
2026-09-21 11:26:00.585653 | ubuntu-noble | + for modulename in $module_names
2026-09-21 11:26:00.585674 | ubuntu-noble | + extract_messages_python find
2026-09-21 11:26:00.585689 | ubuntu-noble | + local modulename=find
2026-09-21 11:26:00.585714 | ubuntu-noble | + local pot=find/locale/find.pot
2026-09-21 11:26:00.585731 | ubuntu-noble | + mkdir -p find/locale
2026-09-21 11:26:00.587835 | ubuntu-noble | + pybabel --quiet extract --add-comments Translators: --msgid-bugs-address=https://bugs.launchpad.net/openstack-i18n/ --project=ceilometer --version= -k _C:1c,2 -k _P:1,2 -o find/locale/find.pot find
2026-09-21 11:26:00.735500 | ubuntu-noble | + check_empty_pot find/locale/find.pot
2026-09-21 11:26:00.735583 | ubuntu-noble | + local pot=find/locale/find.pot
2026-09-21 11:26:00.736501 | ubuntu-noble | ++ msgfmt --statistics -o /dev/null find/locale/find.pot
2026-09-21 11:26:00.742542 | ubuntu-noble | + trans='0 translated messages.'
2026-09-21 11:26:00.742600 | ubuntu-noble | + '[' '0 translated messages.' = '0 translated messages.' ']'
2026-09-21 11:26:00.742613 | ubuntu-noble | + rm find/locale/find.pot
2026-09-21 11:26:00.744877 | ubuntu-noble | + git rm --ignore-unmatch find/locale/find.pot
2026-09-21 11:26:00.749288 | ubuntu-noble | + ALL_MODULES='find releasenotes '
...
2026-09-21 11:26:03.390835 | ubuntu-noble | [INFO] Found source documents:
2026-09-21 11:26:03.390946 | ubuntu-noble | [INFO]            releasenotes/source/locale/releasenotes
2026-09-21 11:26:03.452717 | ubuntu-noble | [WARN] Found 1 obsolete docs on the server which will be DELETED # obsolete docs 감지
2026-09-21 11:26:03.452816 | ubuntu-noble | [INFO] Obsolete docs: [ceilometer/locale/ceilometer]

```

- 2026-09-10
  - [https://zuul.opendev.org/t/openstack/build/77820d2a53ec48678b80156e7a365dfc/log/job-output.txt](https://zuul.opendev.org/t/openstack/build/77820d2a53ec48678b80156e7a365dfc/log/job-output.txt)

```
2026-09-10 11:43:26.440014 | ubuntu-noble | + ALL_MODULES='releasenotes '
2026-09-10 11:43:26.440044 | ubuntu-noble | + for modulename in $module_names
2026-09-10 11:43:26.440050 | ubuntu-noble | + extract_messages_python ceilometer
2026-09-10 11:43:26.440059 | ubuntu-noble | + local modulename=ceilometer
2026-09-10 11:43:26.440066 | ubuntu-noble | + local pot=ceilometer/locale/ceilometer.pot
2026-09-10 11:43:26.440083 | ubuntu-noble | + mkdir -p ceilometer/locale
2026-09-10 11:43:26.442546 | ubuntu-noble | + pybabel --quiet extract --add-comments Translators: --msgid-bugs-address=https://bugs.launchpad.net/openstack-i18n/ --project=ceilometer --version= -k _C:1c,2 -k _P:1,2 -o ceilometer/locale/ceilometer.pot ceilometer
2026-09-10 11:43:26.923698 | ubuntu-noble | + check_empty_pot ceilometer/locale/ceilometer.pot
2026-09-10 11:43:26.923759 | ubuntu-noble | + local pot=ceilometer/locale/ceilometer.pot
2026-09-10 11:43:26.924552 | ubuntu-noble | ++ msgfmt --statistics -o /dev/null ceilometer/locale/ceilometer.pot
2026-09-10 11:43:26.931633 | ubuntu-noble | + trans='0 translated messages, 21 untranslated messages.'
2026-09-10 11:43:26.931658 | ubuntu-noble | + '[' '0 translated messages, 21 untranslated messages.' = '0 translated messages.' ']'
2026-09-10 11:43:26.931666 | ubuntu-noble | + ALL_MODULES='ceilometer releasenotes '
...

2026-09-10 11:43:29.008298 | ubuntu-noble | [INFO] Found source documents:
2026-09-10 11:43:29.008362 | ubuntu-noble | [INFO]            ceilometer/locale/ceilometer
2026-09-10 11:43:29.008380 | ubuntu-noble | [INFO]            releasenotes/source/locale/releasenotes
2026-09-10 11:43:29.117019 | ubuntu-noble | [INFO] pushing source doc [name=ceilometer/locale/ceilometer size=21] to server
2026-09-10 11:43:29.901662 | ubuntu-noble | [INFO] pushing source doc [name=releasenotes/source/locale/releasenotes size=410] to server

```

### designate

- pyproject.toml가 변경된 시점이 오래되었으므로 로그를 확인할 수 없다. 다만 최근 로그를 통해 위와 동일하게 find로 추출됨을 확인했다. 
  - [https://review.opendev.org/c/openstack/designate/+/988097](https://review.opendev.org/c/openstack/designate/+/988097)

```
# 2026-09-30
2026-09-30 14:12:44.538281 | ubuntu-noble | + ALL_MODULES='releasenotes '
2026-09-30 14:12:44.538287 | ubuntu-noble | + for modulename in $module_names
2026-09-30 14:12:44.538290 | ubuntu-noble | + extract_messages_python find
2026-09-30 14:12:44.538294 | ubuntu-noble | + local modulename=find
2026-09-30 14:12:44.538316 | ubuntu-noble | + local pot=find/locale/find.pot
2026-09-30 14:12:44.538319 | ubuntu-noble | + mkdir -p find/locale
2026-09-30 14:12:44.539593 | ubuntu-noble | + pybabel --quiet extract --add-comments Translators: --msgid-bugs-address=https://bugs.launchpad.net/openstack-i18n/ --project=designate --version= -k _C:1c,2 -k _P:1,2 -o find/locale/find.pot find
2026-09-30 14:12:44.593738 | ubuntu-noble | + check_empty_pot find/locale/find.pot
2026-09-30 14:12:44.593785 | ubuntu-noble | + local pot=find/locale/find.pot
2026-09-30 14:12:44.594149 | ubuntu-noble | ++ msgfmt --statistics -o /dev/null find/locale/find.pot
2026-09-30 14:12:44.597376 | ubuntu-noble | + trans='0 translated messages.'
2026-09-30 14:12:44.597410 | ubuntu-noble | + '[' '0 translated messages.' = '0 translated messages.' ']'
2026-09-30 14:12:44.597414 | ubuntu-noble | + rm find/locale/find.pot
2026-09-30 14:12:44.598666 | ubuntu-noble | + git rm --ignore-unmatch find/locale/find.pot
2026-09-30 14:12:44.600465 | ubuntu-noble | + ALL_MODULES='find releasenotes '
...

# 이미 삭제되었으므로 Obsolete docs 관련 로그가 표시되지 않는다. 

```

### ironic, neutron, nova, neutron-lib, python-heatclient, python-openstackclient

- designate와 동일한 upstream-translation-update 로그가 보여준다.
  - 전환 시점의 로그는 보관 기간이 지나 확인할 수 없어, 최신 로그에서 `find`로 추출된다. 


| 프로젝트                   | pyproject.toml 전환 리뷰                                                             | 머지 시각 (UTC)      | 최신 upstream-translation-update 로그                                                                            |
| ---------------------- | -------------------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------ |
| designate              | [988097](https://review.opendev.org/c/openstack/designate/+/988097)              | 2026-05-19 10:26 | [2026-09-30](https://zuul.opendev.org/t/openstack/build/df68274dfc21439db75d07e2a28d9522/log/job-output.txt) |
| ironic                 | [987105](https://review.opendev.org/c/openstack/ironic/+/987105)                 | 2026-05-11 22:12 | [2026-10-01](https://zuul.opendev.org/t/openstack/build/52005b41f51541ffb52ab209316d42d1/log/job-output.txt) |
| neutron                | [988376](https://review.opendev.org/c/openstack/neutron/+/988376)                | 2026-05-14 12:22 | [2026-10-02](https://zuul.opendev.org/t/openstack/build/289d371ae2d84029aa69f07976d4337f/log/job-output.txt) |
| nova                   | [988598](https://review.opendev.org/c/openstack/nova/+/988598)                   | 2026-06-27 03:51 | [2026-10-01](https://zuul.opendev.org/t/openstack/build/12a71d97ec2849a696277034cd561deb/log/job-output.txt) |
| neutron-lib            | [988606](https://review.opendev.org/c/openstack/neutron-lib/+/988606)            | 2026-06-03 10:26 | [2026-10-01](https://zuul.opendev.org/t/openstack/build/01a540487c6841f88cd121cbd6a24658/log/job-output.txt) |
| python-heatclient      | [964885](https://review.opendev.org/c/openstack/python-heatclient/+/964885)      | 2026-08-24 13:25 | [2026-09-25](https://zuul.opendev.org/t/openstack/build/fbf717c4cbd643af98d842874d60f905/log/job-output.txt) |
| python-openstackclient | [979614](https://review.opendev.org/c/openstack/python-openstackclient/+/979614) | 2026-05-02 14:48 | [2026-10-02](https://zuul.opendev.org/t/openstack/build/eed84c4404d9483abb0856b2c1972624/log/job-output.txt) |


## 해결 방안
- `get-modulename.py`스크립트에서 pyproject.toml 추출 관련 로직을 강화한다. 
