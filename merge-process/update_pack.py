import argparse
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
_HERE = Path(__file__).resolve().parent
ROOT = _HERE.parent if _HERE.name == 'merge-process' else _HERE
MERGE = ROOT / 'merge-process'
SRC_URL = 'https://raw.githubusercontent.com/MrKraken/StarStrings/refs/heads/master/src/For_Players/Data/Localization/english/global.ini'
PACKS = {'ScCompLangPack': {'modified': MERGE / 'modified_global.ini', 'fmt': 'default', 'zip': 'ScCompLangPack.zip'}, 'ScCompLangPackRemix2': {'modified': MERGE / 'modified_global_remix2.ini', 'fmt': 'remix2', 'zip': 'ScCompLangPackRemix2.zip'}}
OUT_REL = Path('data/Localization/english/global.ini')
CATS = {'COOL', 'POWR', 'QDRV', 'SHLD', 'RADR', 'QDMP'}
CLASS_FULL = {'Mil': 'Military', 'Civ': 'Civilian', 'Ind': 'Industrial', 'Com': 'Competition', 'Stl': 'Stealth'}
CLASS_FULL_REV = {v: k for k, v in CLASS_FULL.items()}
CLASS_CODE = {'Military': 'MIL', 'Civilian': 'CIV', 'Industrial': 'IND', 'Competition': 'CMP', 'Stealth': 'STL'}

def read_text(path):
    raw = path.read_bytes().decode('utf-8')
    bom = raw.startswith('\ufeff')
    raw = raw.lstrip('\ufeff')
    lines = raw.replace('\r\n', '\n').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return (lines, bom)

def write_text(path, lines, bom=True, eol='\r\n'):
    data = ('\ufeff' if bom else '') + eol.join(lines) + eol
    path.write_bytes(data.encode('utf-8'))

def norm(key):
    return re.sub('^item_name_?', '', key, flags=re.I).lower()

def kv(line):
    return line.split('=', 1) if '=' in line else (None, None)

def download(dest):
    print(f'[1] Downloading global.ini from StarStrings ...')
    req = urllib.request.Request(SRC_URL, headers={'User-Agent': 'ScCompLangPack-updater'})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if len(data) < 1000000:
        sys.exit(f'Download too small ({len(data)} bytes) - aborted')
    dest.write_bytes(data)
    print(f'    {len(data) / 1000000.0:.1f} MB saved: {dest}')

def source_subtitle(global_lines):
    for l in global_lines:
        if l.startswith('Frontend_PU_Version='):
            m = re.search(':\\s*(.*?)\\s*(\\||$)', l.split('=', 1)[1])
            return m.group(1) if m else None
    return None

def set_version(version, subtitle, tag, prerelease):
    print(f'[2] Setting version {version}')
    for p in PACKS.values():
        path = p['modified']
        lines, bom = read_text(path)
        n = 0
        for i, l in enumerate(lines):
            if re.match('Frontend_PU_Version(,P)?=', l):
                key = l.split('=', 1)[0]
                sub = subtitle
                if not sub:
                    m = re.search(':\\s*(.*)$', l.split('=', 1)[1])
                    sub = m.group(1) if m else ''
                lines[i] = f'{key}=Alpha {version}' + (f': {sub}' if sub else '')
                n += 1
            elif l.startswith('Frontend_play_star_citizen,P='):
                l = re.sub('v\\d+(?:\\.\\d+)+', tag, l)
                l = re.sub('\\s*\\[Pre Release\\]\\s*$', '', l)
                lines[i] = l + (' [Pre Release]' if prerelease else '')
                n += 1
        write_text(path, lines, bom)
        print(f'    {path.name}: {n} lines')
    readme = ROOT / 'README.md'
    raw = readme.read_bytes().decode('utf-8')
    new, n = re.subn('\\[🚀[^\\]]*?🚀\\]', f'[🚀{version} OUT🚀]', raw, count=1)
    if n:
        readme.write_bytes(new.encode('utf-8'))
        print('    README.md title updated')

def desc_info(gd, key):
    cands = [re.sub('^([Ii]tem_)[Nn]ame_?', '\\1Desc', key), re.sub('^([Ii]tem_)[Nn]ame_?', '\\1Desc_', key)]
    desc = next((gd[c] for c in cands if c in gd), '')
    cl = re.search('Class: (\\w+)', desc)
    gr = re.search('Grade: (\\w+)', desc)
    sz = re.search('Size: (\\d)', desc)
    grade = gr.group(1) if gr else None
    if grade == 'Bespoke':
        grade = 'B'
    return (cl.group(1) if cl else None, grade, sz.group(1) if sz else None)

def find_new(global_lines):
    have = set()
    for p in PACKS.values():
        lines, _ = read_text(p['modified'])
        have |= {norm(kv(l)[0]) for l in lines if '=' in l}
    gd = dict((kv(l) for l in global_lines if '=' in l))
    auto, manual = ({}, [])
    for key, val in gd.items():
        m = re.match('item_name_?([A-Z]+)_', key, re.I)
        if not m or m.group(1).upper() not in CATS or norm(key) in have:
            continue
        if re.search('_(Controller|Default|short)$', key) or 'PH]' in val or ',P' in key:
            continue
        pm = re.match('(Mil|Civ|Ind|Com|Stl)/(\\d)/(\\w) (.+)$', val)
        if pm:
            auto[key] = (pm.group(4), CLASS_FULL[pm.group(1)], pm.group(3), pm.group(2))
            continue
        cl, gr, sz = desc_info(gd, key)
        if cl in CLASS_CODE and gr:
            s = sz or (re.search('_S(\\d)', key) or [None, '?'])[1]
            auto[key] = (val, cl, gr, s)
        else:
            manual.append(f'{key}={val}')
    return (auto, manual)

def format_line(fmt, key, entry):
    name, cl, gr, sz = entry
    if fmt == 'default':
        return f'{key}={name} {cl} {gr}'
    return f'{key}={CLASS_CODE[cl]}-{sz}{gr} "{name}"'

def insert_sorted(lines, new_line):
    key = kv(new_line)[0]
    cat = norm(key).split('_')[0]
    idx = [i for i, x in enumerate(lines) if '=' in x and norm(kv(x)[0]).split('_')[0] == cat]
    pos = next((i for i in idx if norm(kv(lines[i])[0]) > norm(key)), idx[-1] + 1 if idx else len(lines))
    lines.insert(pos, new_line)

def handle_new(global_lines, add):
    print('[3] Searching for new components ...')
    auto, manual = find_new(global_lines)
    print(f'    {len(auto)} new components with class/grade found')
    for k, e in auto.items():
        print('      ' + format_line('default', k, e))
    if manual:
        print(f'    {len(manual)} without class/grade (check manually):')
        for l in manual:
            print('      ' + l)
    if add and auto:
        for p in PACKS.values():
            lines, bom = read_text(p['modified'])
            for k, e in auto.items():
                insert_sorted(lines, format_line(p['fmt'], k, e))
            write_text(p['modified'], lines, bom)
        print('    -> added to both modified files')
    elif auto:
        print('    (not added - use --add-new to add automatically)')

def merge():
    print('[4] Merging global.ini + modified')
    g_lines, g_bom = read_text(MERGE / 'global.ini')
    for name, p in PACKS.items():
        m_lines, _ = read_text(p['modified'])
        repl = {}
        for l in m_lines:
            if '=' in l:
                k, v = kv(l)
                repl[k.strip()] = v
        out, n = ([], 0)
        for l in g_lines:
            if '=' in l:
                k = l.split('=', 1)[0].strip()
                if k in repl:
                    l = l[:l.index('=') + 1] + repl[k]
                    n += 1
            out.append(l)
        dest = ROOT / name / OUT_REL
        dest.parent.mkdir(parents=True, exist_ok=True)
        write_text(dest, out, bom=True)
        print(f'    {name}: {n} lines replaced -> {dest.relative_to(ROOT)}')

def build_zips():
    print('[5] Building ZIP files')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    zips = []
    for name, p in PACKS.items():
        zpath = dist / p['zip']
        with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
            for f in sorted((ROOT / name).rglob('*')):
                if f.is_file() and f.suffix.lower() != '.lnk':
                    z.write(f, f.relative_to(ROOT / name).as_posix())
        print(f'    {zpath.relative_to(ROOT)} ({zpath.stat().st_size / 1000000.0:.1f} MB)')
        zips.append(zpath)
    return zips

def run(*cmd):
    print('    $ ' + ' '.join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)

def next_tag(hotfix=False):
    r = subprocess.run(['git', 'describe', '--tags', '--abbrev=0'], cwd=ROOT, capture_output=True, text=True)
    last = r.stdout.strip()
    if not re.match('v\\d+(\\.\\d+)+$', last):
        sys.exit('No tag like v0.14.3 found - please pass --tag')
    parts = last[1:].split('.')
    if hotfix:
        if len(parts) < 4:
            parts.append('1')
        else:
            parts[-1] = str(int(parts[-1]) + 1)
    else:
        parts[-1] = str(int(parts[-1]) + 1)
    return 'v' + '.'.join(parts)

def verify():
    print('[4b] Verifying output')
    src, _ = read_text(MERGE / 'global.ini')
    src_map = {}
    for l in src:
        if '=' in l:
            k, v = kv(l)
            src_map[k.strip()] = v
    for name, p in PACKS.items():
        out, _ = read_text(ROOT / name / OUT_REL)
        if len(out) != len(src):
            sys.exit(f'{name}: line count differs from source ({len(out)} vs {len(src)})')
        out_map = {}
        for l in out:
            if '=' in l:
                k, v = kv(l)
                out_map[k.strip()] = v
        m_lines, _ = read_text(p['modified'])
        bad = []
        for l in m_lines:
            if '=' in l:
                k, v = kv(l)
                k = k.strip()
                if k in src_map and out_map.get(k) != v:
                    bad.append(k)
        if bad:
            sys.exit(f'{name}: {len(bad)} entries differ from modified file, e.g. {bad[:3]}')
        extra = [k for k in out_map if k in src_map and out_map[k] != src_map[k] and k not in {kv(x)[0].strip() for x in m_lines if '=' in x}]
        if extra:
            sys.exit(f'{name}: {len(extra)} unexpected differences from source, e.g. {extra[:3]}')
    print('    OK')

def current_version():
    lines, _ = read_text(PACKS['ScCompLangPack']['modified'])
    for l in lines:
        m = re.match('Frontend_PU_Version=Alpha (\\S+?):?(\\s|$)', l)
        if m:
            return m.group(1).rstrip(':')
    sys.exit('Frontend_PU_Version not found in modified_global.ini')

def check():
    req = urllib.request.Request(SRC_URL, headers={'User-Agent': 'ScCompLangPack-updater'})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = r.read()
    if len(data) < 1000000:
        sys.exit(f'Download too small ({len(data)} bytes) - aborted')
    new = data.decode('utf-8').lstrip('\ufeff').replace('\r\n', '\n')
    old = (MERGE / 'global.ini').read_bytes().decode('utf-8').lstrip('\ufeff').replace('\r\n', '\n')
    version = current_version()
    if new == old:
        status = 'unchanged'
    else:
        base = None
        for l in new.split('\n'):
            if l.startswith('Frontend_PU_Version='):
                m = re.search('Alpha (\\d+(?:\\.\\d+)*)', l)
                base = m.group(1) if m else None
                break
        status = 'changed' if base and (version == base or version.startswith(base + '.')) else 'newversion'
    print(f'status={status} version={version}')
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f'status={status}\nversion={version}\n')

def publish(version, zips, prerelease, tag, notes, yes=False):
    title = f'{version} - {tag}'
    notes = notes or (f'{version} PTU\nThis is a PTU Version, expect missing Text' if prerelease else f'{version} release')
    msg = f'{version} [pre release]' if prerelease else f'{version} update'
    print('\n[6] Publishing')
    subprocess.run(['git', 'status', '--short'], cwd=ROOT)
    print(f"    Commit message: {msg}\n    Release:          {title} (Tag {tag}){(' [Pre-release]' if prerelease else '')}\n    Notes:            {notes!r}\n    Assets:           " + ', '.join((z.name for z in zips)))
    if not yes and input('Run commit, push and release now? [y/N] ').strip().lower() not in ('y', 'j'):
        print('Aborted - nothing pushed. ZIPs are in dist/.')
        return
    run('git', 'add', '-A')
    run('git', 'commit', '-m', msg)
    run('git', 'push')
    cmd = ['gh', 'release', 'create', tag, *[str(z) for z in zips], '--repo', 'ExoAE/ScCompLangPack', '--target', 'main', '--title', title, '--notes', notes]
    if prerelease:
        cmd.append('--prerelease')
    run(*cmd)
    print('Done.')

def main():
    ap = argparse.ArgumentParser(description='ScCompLangPack update automation')
    ap.add_argument('version', nargs='?', help='New game version, e.g. 4.10.4')
    ap.add_argument('--subtitle', help="Title suffix, e.g. 'Siege of Orison' (default: from StarStrings)")
    ap.add_argument('--no-download', action='store_true', help='use the existing merge-process/global.ini')
    ap.add_argument('--add-new', action='store_true', help='add new components automatically')
    ap.add_argument('--no-release', action='store_true', help='no commit/push/release')
    ap.add_argument('--prerelease', action='store_true')
    ap.add_argument('--hotfix', action='store_true', help='default tag: append/increment a 4th number (v0.14.3 -> v0.14.3.1)')
    ap.add_argument('--yes', action='store_true', help='do not ask before commit/push/release')
    ap.add_argument('--check', action='store_true', help='only report whether StarStrings changed (unchanged/changed/newversion)')
    ap.add_argument('--tag', help='Release tag, e.g. v0.14.4 (default: last tag + 1)')
    ap.add_argument('--notes', help="Release notes (default: '<version> release' or PTU text)")
    a = ap.parse_args()
    if a.check:
        check()
        return
    if not a.version:
        ap.error('version is required')
    if not a.no_download:
        download(MERGE / 'global.ini')
    g_lines, _ = read_text(MERGE / 'global.ini')
    tag = a.tag or next_tag(a.hotfix)
    print(f'Pack version/tag: {tag}')
    set_version(a.version, a.subtitle or source_subtitle(g_lines), tag, a.prerelease)
    handle_new(g_lines, a.add_new)
    merge()
    verify()
    zips = build_zips()
    if not a.no_release:
        publish(a.version, zips, a.prerelease, tag, a.notes, a.yes)
if __name__ == '__main__':
    main()
