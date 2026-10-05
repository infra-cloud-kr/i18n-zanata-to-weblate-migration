# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Plural rules extracted from Zanata.

Ref:
- https://github.com/zanata/zanata-platform/blob/master/server/services/
src/main/resources/pluralforms.properties
"""

ZANATA_LANG_RULES = {
    'ach': {
        'region_code': ['ach'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'af': {
        'region_code': ['af'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ak': {
        'region_code': ['ak'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'am': {
        'region_code': ['am'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'an': {
        'region_code': ['an'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'anp': {
        'region_code': ['anp'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ar': {
        'region_code': ['ar'],
        'plurals': (
            'nplurals=6; plural= n==0 ? 0 : n==1 ? 1 : n==2 ? 2 : '
            'n%100>=3 && n%100<=10 ? 3 : n%100>=11 ? 4 : 5;'
        )
    },
    'arn': {
        'region_code': ['arn'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'as': {
        'region_code': ['as'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ast': {
        'region_code': ['ast'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ay': {
        'region_code': ['ay'],
        'plurals': 'nplurals=1; plural=0'
    },
    'az': {
        'region_code': ['az'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'be': {
        'region_code': ['be'],
        'plurals': (
            'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : '
            'n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2)'
        )
    },
    'bg': {
        'region_code': ['bg_BG'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'bn': {
        'region_code': ['bn', 'bn_IN'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'bo': {
        'region_code': ['bo'],
        'plurals': 'nplurals=1; plural=0'
    },
    'br': {
        'region_code': ['br'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'brx': {
        'region_code': ['brx'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'bs': {
        'region_code': ['bs'],
        'plurals': (
            'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : '
            'n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2)'
        )
    },
    'ca': {
        'region_code': ['ca'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'cgg': {
        'region_code': ['cgg'],
        'plurals': 'nplurals=1; plural=0'
    },
    'cs': {
        'region_code': ['cs'],
        'plurals': (
            'nplurals=3; plural=(n==1) ? 0 : (n>=2 && n<=4) ? 1 : 2'
        )
    },
    'csb': {
        'region_code': ['csb'],
        'plurals': (
            'nplurals=3; n==1 ? 0 : n%10>=2 && n%10<=4 && '
            '(n%100<10 || n%100>=20) ? 1 : 2'
        )
    },
    'cy': {
        'region_code': ['cy'],
        'plurals': (
            'nplurals=4; plural= (n==1) ? 0 : (n==2) ? 1 : '
            '(n != 8 && n != 11) ? 2 : 3'
        )
    },
    'da': {
        'region_code': ['da'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'de': {
        'region_code': ['de'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'doi': {
        'region_code': ['doi'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'dz': {
        'region_code': ['dz'],
        'plurals': 'nplurals=1; plural=0'
    },
    'el': {
        'region_code': ['el'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'en': {
        'region_code': ['en_US', 'en_GB', 'en_AU'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'eo': {
        'region_code': ['eo'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'es': {
        'region_code': ['es', 'es_MX'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'et': {
        'region_code': ['et'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'eu': {
        'region_code': ['eu'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'fa': {
        'region_code': ['fa'],
        'plurals': 'nplurals=1; plural=0'
    },
    'fi': {
        'region_code': ['fi_FI'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'fil': {
        'region_code': ['fil'],
        'plurals': 'nplurals=2; plural=n > 1'
    },
    'fo': {
        'region_code': ['fo'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'fr': {
        'region_code': ['fr'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'fur': {
        'region_code': ['fur'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'fy': {
        'region_code': ['fy'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ga': {
        'region_code': ['ga'],
        'plurals': (
            'nplurals=5; plural= n==1 ? 0 : n==2 ? 1 : n<7 ? 2 : n<11 ? 3 : 4'
        )
    },
    'gd': {
        'region_code': ['gd'],
        'plurals': (
            'nplurals=4; plural=(n==1 || n==11) ? 0 : (n==2 || '
            'n==12) ? 1 : (n > 2 && n < 20) ? 2 : 3'
        )
    },
    'gl': {
        'region_code': ['gl'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'gu': {
        'region_code': ['gu'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'gun': {
        'region_code': ['gun'],
        'plurals': 'nplurals=2; plural = (n > 1)'
    },
    'ha': {
        'region_code': ['ha'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'he': {
        'region_code': ['he'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'hi': {
        'region_code': ['hi'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'hne': {
        'region_code': ['hne'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'hy': {
        'region_code': ['hy'],
        'plurals': 'nplurals=1; plural=0'
    },
    'hr': {
        'region_code': ['hr'],
        'plurals': (
            'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : '
            'n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2)'
        )
    },
    'hu': {
        'region_code': ['hu'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ia': {
        'region_code': ['ia'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'id': {
        'region_code': ['id'],
        'plurals': 'nplurals=1; plural=0'
    },
    'is': {
        'region_code': ['is'],
        'plurals': 'nplurals=2; plural=(n%10!=1 || n%100==11)'
    },
    'it': {
        'region_code': ['it'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ja': {
        'region_code': ['ja'],
        'plurals': 'nplurals=1; plural=0'
    },
    'jbo': {
        'region_code': ['jbo'],
        'plurals': 'nplurals=1; plural=0'
    },
    'jv': {
        'region_code': ['jv'],
        'plurals': 'nplurals=2; plural=n!=0'
    },
    'ka': {
        'region_code': ['ka_GE'],
        'plurals': 'nplurals=1; plural=0'
    },
    'kk': {
        'region_code': ['kk'],
        'plurals': 'nplurals=1; plural=0'
    },
    'km': {
        'region_code': ['km'],
        'plurals': 'nplurals=1; plural=0'
    },
    'kn': {
        'region_code': ['kn'],
        'plurals': 'nplurals=2; plural=(n!=1)'
    },
    'ko': {
        'region_code': ['ko_KR'],
        'plurals': 'nplurals=1; plural=0'
    },
    'kok': {
        'region_code': ['kok'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ks': {
        'region_code': ['ks'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ku': {
        'region_code': ['ku'],
        'plurals': 'nplurals=2; plural=(n!= 1)'
    },
    'kw': {
        'region_code': ['kw'],
        'plurals': (
            'nplurals=4; plural= (n==1) ? 0 : (n==2) ? 1 : (n == 3) ? 2 : 3'
        )
    },
    'ky': {
        'region_code': ['ky'],
        'plurals': 'nplurals=1; plural=0'
    },
    'lb': {
        'region_code': ['lb'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ln': {
        'region_code': ['ln'],
        'plurals': 'nplurals=2; plural=n>1;'
    },
    'lo': {
        'region_code': ['lo'],
        'plurals': 'nplurals=1; plural=0'
    },
    'lt': {
        'region_code': ['lt'],
        'plurals': (
            'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : '
            'n%10>=2 && (n%100<10 || n%100>=20) ? 1 : 2)'
        )
    },
    'lv': {
        'region_code': ['lv'],
        'plurals': (
            'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n != 0 ? 1 : 2)'
        )
    },
    'mai': {
        'region_code': ['mai'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'me': {
        'region_code': ['me'],
        'plurals': (
            'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : '
            'n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2)'
        )
    },
    'mfe': {
        'region_code': ['mfe'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'mg': {
        'region_code': ['mg'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'mi': {
        'region_code': ['mi'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'mk': {
        'region_code': ['mk'],
        'plurals': 'nplurals=2; plural= n==1 || n%10==1 ? 0 : 1'
    },
    'ml': {
        'region_code': ['ml'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'mn': {
        'region_code': ['mn'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'mni': {
        'region_code': ['mni'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'mnk': {
        'region_code': ['mnk'],
        'plurals': 'nplurals=3; plural=(n==0 ? 0 : n==1 ? 1 : 2'
    },
    'mr': {
        'region_code': ['mr'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ms': {
        'region_code': ['ms'],
        'plurals': 'nplurals=1; plural=0'
    },
    'mt': {
        'region_code': ['mt'],
        'plurals': (
            'nplurals=4; plural=(n==1 ? 0 : n==0 || ( n%100>1 && '
            'n%100<11) ? 1 : (n%100>10 && n%100<20 ) ? 2 : 3)'
        )
    },
    'nah': {
        'region_code': ['nah'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'nap': {
        'region_code': ['nap'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'nb': {
        'region_code': ['nb'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ne': {
        'region_code': ['ne'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'nl': {
        'region_code': ['nl_NL'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'se': {
        'region_code': ['se'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'nn': {
        'region_code': ['nn'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'no': {
        'region_code': ['no'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'nso': {
        'region_code': ['nso'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'oc': {
        'region_code': ['oc'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'or': {
        'region_code': ['or'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ps': {
        'region_code': ['ps'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'pa': {
        'region_code': ['pa_IN'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'pap': {
        'region_code': ['pap'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'pl': {
        'region_code': ['pl_PL'],
        'plurals': (
            'nplurals=3; plural=(n==1 ? 0 : n%10>=2 && n%10<=4 && '
            '(n%100<10 || n%100>=20) ? 1 : 2)'
        )
    },
    'pms': {
        'region_code': ['pms'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'pt': {
        'region_code': ['pt', 'pt_BR'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'pt_BR': {
        'region_code': 'BR',
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'rm': {
        'region_code': ['rm'],
        'plurals': 'nplurals=2; plural=(n!=1);'
    },
    'ro': {
        'region_code': ['ro'],
        'plurals': (
            'nplurals=3; plural=(n==1 ? 0 : (n==0 || (n%100 > 0 && '
            'n%100 < 20)) ? 1 : 2);'
        )
    },
    'ru': {
        'region_code': ['ru'],
        'plurals': (
            'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : '
            'n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2)'
        )
    },
    'sa': {
        'region_code': ['sa'],
        'plurals': 'nplurals=3; plural=( n==1 ? 0 : n==2 ? 1 : 2 )'
    },
    'sat': {
        'region_code': ['sat'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'sco': {
        'region_code': ['sco'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'sd': {
        'region_code': ['sd'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'si': {
        'region_code': ['si'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'sk': {
        'region_code': ['sk'],
        'plurals': 'nplurals=3; plural=(n==1) ? 0 : (n>=2 && n<=4) ? 1 : 2'
    },
    'sl': {
        'region_code': ['sl_SI'],
        'plurals': (
            'nplurals=4; plural=(n%100==1 ? 1 : n%100==2 ? '
            '2 : n%100==3 || n%100==4 ? 3 : 0)'
        )
    },
    'so': {
        'region_code': ['so'],
        'plurals': 'nplurals=2; plural=n != 1'
    },
    'son': {
        'region_code': ['son'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'sq': {
        'region_code': ['sq'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'sr': {
        'region_code': ['sr'],
        'plurals': (
            'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : '
            'n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2)'
        )
    },
    'su': {
        'region_code': ['su'],
        'plurals': 'nplurals=1; plural=0'
    },
    'sw': {
        'region_code': ['sw'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'sv': {
        'region_code': ['sv'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'ta': {
        'region_code': ['ta'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'te': {
        'region_code': ['te_IN'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'tg': {
        'region_code': ['tg'],
        'plurals': 'nplurals=1; plural=0'
    },
    'ti': {
        'region_code': ['ti'],
        'plurals': 'nplurals=2; plural=n > 1'
    },
    'th': {
        'region_code': ['th'],
        'plurals': 'nplurals=1; plural=0'
    },
    'tk': {
        'region_code': ['tk'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'tr': {
        'region_code': ['tr_TR'],
        'plurals': 'nplurals=2; plural=(n>1)'
    },
    'tt': {
        'region_code': ['tt'],
        'plurals': 'nplurals=1; plural=0'
    },
    'ug': {
        'region_code': ['ug'],
        'plurals': 'nplurals=1; plural=0;'
    },
    'uk': {
        'region_code': ['uk'],
        'plurals': (
            'nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : '
            'n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2)'
        )
    },
    'ur': {
        'region_code': ['ur'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'uz': {
        'region_code': ['uz'],
        'plurals': 'nplurals=1; plural=0;'
    },
    'vi': {
        'region_code': ['vi_VN'],
        'plurals': 'nplurals=1; plural=0'
    },
    'wa': {
        'region_code': ['wa'],
        'plurals': 'nplurals=2; plural=(n > 1)'
    },
    'wo': {
        'region_code': ['wo'],
        'plurals': 'nplurals=1; plural=0'
    },
    'yo': {
        'region_code': ['yo'],
        'plurals': 'nplurals=2; plural=(n != 1)'
    },
    'zh': {
        'region_code': ['zh_CN', 'zh_TW'],
        'plurals': 'nplurals=1; plural=0'
    },
}
