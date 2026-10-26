"""Claude Design(.dc) 템플릿 → React JSX 변환기.

인라인 style, sc-if/sc-for, {{ }} 바인딩, sc-camel-on-* 핸들러, style-hover/focus 를
그대로 JSX 로 옮긴다. 마크업과 스타일 값은 원본과 1:1 이다.

사용: python dc2jsx.py <template.html> <out.tsx> <ComponentName> <assetMapJson> <cssOut> [--root-override]
"""
import html
import json
import re
import sys
from html.parser import HTMLParser

VOID = {'img', 'input', 'br', 'meta', 'link', 'hr', 'source'}
EVENT = {
    'sc-camel-on-click': 'onClick', 'sc-camel-on-change': 'onChange', 'sc-camel-on-drop': 'onDrop',
    'sc-camel-on-drag-over': 'onDragOver', 'sc-camel-on-drag-leave': 'onDragLeave', 'sc-camel-on-scroll': 'onScroll',
    'sc-camel-on-input': 'onInput', 'sc-camel-on-key-down': 'onKeyDown', 'sc-camel-on-blur': 'onBlur', 'sc-camel-on-focus': 'onFocus',
}
ATTR_RENAME = {
    'class': 'className', 'for': 'htmlFor', 'autoplay': 'autoPlay', 'playsinline': 'playsInline', 'inputmode': 'inputMode',
    'sc-camel-view-box': 'viewBox', 'sc-camel-preserve-aspect-ratio': 'preserveAspectRatio', 'tabindex': 'tabIndex',
    'readonly': 'readOnly', 'maxlength': 'maxLength', 'autocomplete': 'autoComplete', 'crossorigin': 'crossOrigin',
    'stroke-width': 'strokeWidth', 'stroke-linecap': 'strokeLinecap', 'stroke-linejoin': 'strokeLinejoin',
    'stroke-dasharray': 'strokeDasharray', 'stroke-dashoffset': 'strokeDashoffset', 'font-family': 'fontFamily',
    'font-size': 'fontSize', 'font-weight': 'fontWeight', 'text-anchor': 'textAnchor', 'dominant-baseline': 'dominantBaseline',
    'fill-opacity': 'fillOpacity', 'stroke-opacity': 'strokeOpacity', 'clip-path': 'clipPath', 'stop-color': 'stopColor',
    'stop-opacity': 'stopOpacity', 'xlink:href': 'xlinkHref', 'vector-effect': 'vectorEffect', 'letter-spacing': 'letterSpacing',
}
BOOL_ATTRS = {'autoPlay', 'muted', 'loop', 'playsInline', 'controls', 'disabled', 'checked', 'readOnly', 'hidden'}
BIND = re.compile(r'\{\{\s*(.*?)\s*\}\}')


class Node:
    def __init__(self, tag, attrs):
        self.tag = tag
        self.attrs = attrs
        self.children = []


class Text:
    def __init__(self, s):
        self.s = s


class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.root = Node('#root', [])
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs)
        self.stack[-1].children.append(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, d):
        self.stack[-1].children.append(Text(d))

    def handle_entityref(self, name):
        self.stack[-1].children.append(Text(f'&{name};'))

    def handle_charref(self, name):
        self.stack[-1].children.append(Text(f'&#{name};'))


def css_prop(p):
    p = p.strip()
    if p.startswith('--'):
        return json.dumps(p)
    if p.startswith('-webkit-'):
        p = 'Webkit-' + p[8:]
    elif p.startswith('-moz-'):
        p = 'Moz-' + p[5:]
    elif p.startswith('-ms-'):
        p = 'ms-' + p[4:]
    parts = p.split('-')
    out = parts[0] + ''.join(x[:1].upper() + x[1:] for x in parts[1:])
    return out


def split_decls(s):
    """세미콜론으로 선언을 나눈다. 괄호 안의 세미콜론은 보호."""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ';' and depth == 0:
            out.append(cur)
            cur = ''
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return [d for d in out if d.strip()]


class Conv:
    def __init__(self, assets, prefix):
        self.assets = assets
        self.prefix = prefix
        self.hover = {}
        self.focus = {}
        self.css = []

    # ----- 표현식 -----
    def expr(self, e, scope):
        e = e.strip()
        if e in ('true', 'false', 'null'):
            return e
        head = e.split('.')[0]
        if head in scope:
            return e
        return 'v.' + e

    def interp(self, s, scope):
        """'a {{ x }} b' → JS 식 문자열. 전부 바인딩이면 식 그대로, 섞이면 템플릿 리터럴."""
        parts = BIND.split(s)
        if len(parts) == 1:
            return json.dumps(html.unescape(s), ensure_ascii=False)
        if len(parts) == 3 and parts[0] == '' and parts[2] == '':
            return self.expr(parts[1], scope)
        out = '`'
        for i, p in enumerate(parts):
            if i % 2 == 0:
                out += html.unescape(p).replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')
            else:
                out += '${' + self.expr(p, scope) + '}'
        return out + '`'

    def style_obj(self, s, scope):
        items = []
        for d in split_decls(s):
            if ':' not in d:
                continue
            k, val = d.split(':', 1)
            items.append(f'{css_prop(k)}: {self.interp(val.strip(), scope)}')
        return '{ ' + ', '.join(items) + ' }'

    def pseudo_class(self, kind, decl):
        reg = self.hover if kind == 'hover' else self.focus
        if decl not in reg:
            reg[decl] = f'{self.prefix}-{kind[0]}{len(reg)}'
            rules = ';'.join(f'{d.strip()} !important' for d in split_decls(decl))
            self.css.append(f'.{reg[decl]}:{kind}{{{rules}}}')
        return reg[decl]

    # ----- 노드 -----
    def attrs(self, node, scope, root_override=False):
        out = []
        classes = []
        for k, val in node.attrs:
            if val is None:
                val = ''
            if k.startswith('hint-placeholder'):
                continue
            if k == 'style':
                obj = self.style_obj(val, scope)
                if root_override:
                    obj = '{ ...' + obj + ', ...(v.rootStyle || {}) }'
                out.append(f'style={{{obj}}}')
                continue
            if k == 'style-hover':
                classes.append(self.pseudo_class('hover', val))
                continue
            if k == 'style-focus':
                classes.append(self.pseudo_class('focus', val))
                continue
            if k in EVENT:
                m = BIND.fullmatch(val.strip())
                out.append(f'{EVENT[k]}={{{self.expr(m.group(1), scope)}}}')
                continue
            if k == 'ref':
                m = BIND.fullmatch(val.strip())
                out.append(f'ref={{{self.expr(m.group(1), scope)}}}')
                continue
            if k in ('src', 'href') and val in self.assets:
                out.append(f'{k}={json.dumps(self.assets[val])}')
                continue
            if k == 'class':
                classes.extend(val.split())
                continue
            name = ATTR_RENAME.get(k, k)
            if name in BOOL_ATTRS and val == '':
                out.append(name)
                continue
            if BIND.search(val):
                out.append(f'{name}={{{self.interp(val, scope)}}}')
            else:
                out.append(f'{name}={json.dumps(html.unescape(val), ensure_ascii=False)}')
        if classes:
            out.append(f'className={json.dumps(" ".join(classes))}')
        return (' ' + ' '.join(out)) if out else ''

    def text(self, t, scope):
        s = t.s
        if not s.strip():
            if '\n' in s:
                return ''
            return '{" "}'
        # HTML 공백 규칙: 연속 공백은 한 칸. 줄바꿈이 낀 앞뒤 공백은 지운다
        s = re.sub(r'[ \t\r\n]+', ' ', s)
        if '\n' in t.s[: len(t.s) - len(t.s.lstrip())]:
            s = s.lstrip()
        if '\n' in t.s[len(t.s.rstrip()):]:
            s = s.rstrip()
        if not s:
            return ''
        parts = BIND.split(s)
        out = ''
        for i, p in enumerate(parts):
            if i % 2 == 0:
                if p:
                    out += '{' + json.dumps(html.unescape(p), ensure_ascii=False) + '}'
            else:
                out += '{' + self.expr(p, scope) + '}'
        return out

    def raw_text(self, n):
        out = ''
        for c in n.children:
            out += c.s if isinstance(c, Text) else (' '.join(v or '' for _, v in c.attrs) + self.raw_text(c))
        return ' '.join(v or '' for _, v in n.attrs) + out

    def clone(self, n, ren):
        def sub(s):
            for a, b in ren.items():
                s = re.sub(r'\{\{\s*' + a + r'\s*\}\}', '{{ ' + b + ' }}', s)
            return s
        if isinstance(n, Text):
            return Text(sub(n.s))
        m = Node(n.tag, [(k, sub(v) if v else v) for k, v in n.attrs])
        m.children = [self.clone(c, ren) for c in n.children]
        return m

    def children(self, node, scope, depth):
        return ''.join(self.node(c, scope, depth) for c in node.children)

    def node(self, n, scope, depth, root_override=False):
        if isinstance(n, Text):
            return self.text(n, scope)
        tag = n.tag
        a = dict(n.attrs)
        if tag == 'sc-if':
            cond = self.expr(BIND.fullmatch(a['value'].strip()).group(1), scope)
            inner = self.children(n, scope, depth)
            return '{' + cond + ' ? (<>' + inner + '</>) : null}'
        if tag == 'sc-for':
            lst = self.expr(BIND.fullmatch(a['list'].strip()).group(1), scope)
            var = a['as']
            idx = '_i' + str(depth)
            inner = self.children(n, scope | {var}, depth + 1)
            return '{(' + lst + ' || []).map((' + var + ': any, ' + idx + ': number) => (<Fragment key={' + idx + '}>' + inner + '</Fragment>))}'
        if a.get('data-jump') is not None:
            return ''
        # 로그인 화면: 아이디 칸 앞에 같은 모양의 '기관 코드' 칸을 하나 더 둔다(API 가 institution_code 를 요구)
        if tag == 'label' and 'loginIdLabel' in self.raw_text(n) and not getattr(n, '_injected', False):
            clone = self.clone(n, {'loginIdLabel': 'loginCodeLabel', 'fLoginId': 'fLoginCode', 'onLoginId': 'onLoginCode', 'loginIdPh': 'loginCodePh'})
            clone._injected = True
            n._injected = True
            return self.node(clone, scope, depth) + self.node(n, scope, depth)
        attrs = self.attrs(n, scope, root_override)
        if tag in VOID:
            return f'<{tag}{attrs} />'
        inner = self.children(n, scope, depth)
        if tag == 'textarea' and inner:
            inner = ''
        return f'<{tag}{attrs}>{inner}</{tag}>'


def main():
    src, out, name, amap, cssout = sys.argv[1:6]
    root_override = '--root-override' in sys.argv
    sel = None
    for arg in sys.argv[6:]:
        if arg.startswith('--select='):
            sel = arg.split('=', 1)[1]
    t = open(src, encoding='utf-8').read()
    t = re.sub(r'<script type="text/x-dc".*?</script>', '', t, flags=re.S)
    m = re.search(r'<x-dc>(.*?)</x-dc>', t, re.S)
    body = re.sub(r'<helmet>.*?</helmet>', '', m.group(1), flags=re.S)
    p = P()
    p.feed(body)
    assets = json.load(open(amap, encoding='utf-8'))
    conv = Conv(assets, name.lower())
    tops = [c for c in p.root.children if isinstance(c, Node)]
    # 앱: 캔버스 안의 프레임(div[data-screen-label])만 쓴다
    if sel == 'frame':
        def find(n):
            if isinstance(n, Node):
                if dict(n.attrs).get('data-screen-label'):
                    return n
                for c in n.children:
                    r = find(c)
                    if r:
                        return r
            return None
        frame = find(p.root)
        tops = [c for c in tops if c.tag == 'svg'] + [frame]
    pieces = []
    for n in tops:
        is_root = dict(n.attrs).get('data-screen-label') is not None
        pieces.append(conv.node(n, set(), 0, root_override=root_override and is_root))
    jsx = ''.join(pieces)
    code = f'''/* eslint-disable */
// 자동 생성 파일. 디자인 템플릿(Paw oh Paw {name})을 dc2jsx.py 로 옮긴 것이다. 손으로 고치지 않는다.
import {{ Fragment }} from 'react'

export type Vals = Record<string, any>

export function {name}({{ v }}: {{ v: Vals }}) {{
  return (<>{jsx}</>)
}}
'''
    open(out, 'w', encoding='utf-8', newline='\n').write(code)
    open(cssout, 'w', encoding='utf-8', newline='\n').write(
        f'/* 자동 생성. {name} 의 style-hover / style-focus. 인라인 스타일을 이기려고 !important 를 쓴다 */\n' + '\n'.join(conv.css) + '\n')
    print(name, 'jsx chars', len(jsx), 'hover', len(conv.hover), 'focus', len(conv.focus))


main()
